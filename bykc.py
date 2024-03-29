from buaa import bykc
import buaa
import argparse
import time
import datetime
import json

TRAVEL_TIME = 60
RETRY_LIMIT = 32
DEFAULT_INTERVAL = 1
SCAN_INTERVAL = 60  # seconds

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-h', '--help', action='help', help='To show help.')
parser.add_argument('username', help='The unified identity authentication account.')
parser.add_argument('password', help='Password of the account.')
parser.add_argument('enroll', nargs='*', type=int, default=[], help='The IDs of courses to enroll.')
parser.add_argument('-V', '--vpn', default=None, type=str, help='The index of VPN used.')
parser.add_argument('-l', '--list', action='store_true',
                    help='To show course list. If this switch is used with -t or --time, the target list will be '
                         'ignored and replaced by course list.')
parser.add_argument('-c', '--chosen', action='store_true',
                    help='To show courses already enrolled in. If this switch is used with -l or --list, courses not '
                         'enrolled in will be showed.')
parser.add_argument('-f', '--forecast', action='store_true',
                    help='To show courses in the forecast list. If -f is used with -l, courses in the forecast list '
                         'will also be grabbed. The software provider assumes NO liability for any behavior that '
                         'breaks rules.')
parser.add_argument('-d', '--drop', nargs='*', default=[], metavar='id', type=int,
                    help='The IDs of courses to drop.')
parser.add_argument('-t', '--time', default=None, type=float, metavar='interval',
                    help='The interval between tries of enrolling. When this option is set, the script will continue '
                         'trying until all targets are enrolled in.')
parser.add_argument('-C', '--continuous', action='count', default=0,
                    help='If this switch is on, the script will continuously attempt to enroll in courses available. '
                         'If this switch is used twice with -l and -t, the script will automatically output notice '
                         'when new courses become selectable instead of enrolling; if -m is also passed, notice '
                         'messages will be sent.')
parser.add_argument('-n', '--number', default=None, type=int, metavar='amount',
                    help='The amount of courses to be enrolled.')
parser.add_argument('-p', '--position', default=None, type=str, metavar='sx',
                    help='The desired campus. \'s\' refers to Shahe, and \'x\' refers to Xueyuanroad. Choices'
                         ' can be combined like \'sx\'. This option is only active when -l and -t are passed. '
                         'It\'s worth notice that since campus is inferred by classroom name, mistakes '
                         'might happen.')
parser.add_argument('-s', '--safe', nargs='?', default=NotImplemented, type=float, metavar='time',
                    help='Safe mode. When this switch is on, the script will never attempt to enroll in a course '
                         'in conflict with regular course timetable. If time is specified, a travel time is taken into '
                         'consideration, ensuring safety of a higher level. The default estimated travel time is '
                         f'{TRAVEL_TIME} (minutes).')
parser.add_argument('-m', '--mail', nargs=2, default=None, type=str, metavar=('account@example.com', 'password'),
                    help='The mail account applied to send reminder email. Setting an email address indicates sending '
                         'a reminder when a target course is successfully enrolled in.')
parser.add_argument('-S', '--server', type=str, default=None, metavar='smtp.example.com',
                    help='The SMTP server of the mail system. Automatically inferred if not given.')
parser.add_argument('-r', '--receiver', type=str, default=None, metavar='receiver@example.com',
                    help='The receiver of the reminder. The reminder will be sent to the sender account if not given.')
parser.add_argument('-R', '--retry', type=int, default=RETRY_LIMIT, metavar='limit',
                    help='The retry limit. The script will automatically retry when connection is aborted unexpectedly'
                         f'. The default retry limit is {RETRY_LIMIT}.')
parser.add_argument('--scan', default=None, type=int, metavar='span',
                    help=f'The span to scan forward for discovering hidden courses.')
parser.add_argument('--default', action='store_true',
                    help=f'The recommended default settings. This switch is synonymous with `-C -l -t '
                         f'{DEFAULT_INTERVAL} -s {TRAVEL_TIME}`.')


def main():
    args = parser.parse_args()

    if args.default:
        setattr(args, 'continuous', getattr(args, 'continuous', 0) + 1)
        setattr(args, 'list', True)
        if args.time is None:
            setattr(args, 'time', DEFAULT_INTERVAL)
        if args.safe is None:
            setattr(args, 'safe', TRAVEL_TIME)

    try:
        vpn = getattr(args, 'vpn', None)

        retry_limit = getattr(args, 'retry', RETRY_LIMIT)

        mail = args.mail
        to_send = False
        if mail is not None:
            to_send = True
            sender, password = mail
            server = args.server
            receiver = args.receiver

        b = bykc(args.username, args.password, type=vpn, retry_limit=retry_limit)

        safety_list = None
        safe_span = datetime.timedelta(minutes=TRAVEL_TIME)
        if args.safe is not NotImplemented:
            j = buaa.jwxt(args.username, args.password, type=vpn)
            year = time.localtime().tm_year
            safety_list = j.timetable(year, buaa.jwxt.semester_infer())
            if args.safe:
                safe_span = datetime.timedelta(minutes=max(args.safe, 0))

        position = args.position
        is_forecast = args.forecast

        def scan(min_, max_):
            res = {}
            for e in range(min_, max_):
                try:
                    detail = b.detail(e)
                except buaa.BUAAException:
                    continue
                except json.decoder.JSONDecodeError:
                    continue
                start_time = detail.start
                if args.safe != NotImplemented:
                    start_time -= datetime.timedelta(minutes=args.safe)
                if start_time > datetime.datetime.now():
                    res[e] = detail
            return res

        scan_cache = (None, None)
        scan_interval = datetime.timedelta(seconds=SCAN_INTERVAL)

        def available_list():
            nonlocal safety_list, safe_span, position, is_forecast, scan_cache
            sel = b.selectable
            if is_forecast:
                sel.update(b.forecast)
            course_list = set(sel.keys())
            if course_list and args.scan:
                min_id = min(course_list)
                max_id = max(course_list) + args.scan
                now = datetime.datetime.now()
                if scan_cache[0] is None or scan_cache[0] + scan_interval < now:
                    scan_res = scan(min_id, max_id)
                    scan_cache = (now, scan_res)
                else:
                    scan_res = scan_cache[1]
                course_list.update(scan_res.keys())
                sel.update(scan_res)
            chosen = set(b.chosen.keys())
            res: set = course_list.difference(chosen)
            if position is not None:
                _res = []
                for c in res:
                    if sel[c].position in position:
                        _res.append(c)
                res = _res
            if safety_list:
                _res = []
                for c in res:
                    d = sel[c].start
                    dt = sel[c].end - d
                    if buaa.jwxt._schedule_available(d, dt, safety_list, safe_span):
                        _res.append(c)
                res = _res
            return list(res)

        if args.forecast:
            fore = b.forecast
            if fore:
                for k, v in fore.items():
                    print(v, end='')
            else:
                print('No upcoming course.')

        ch = b.chosen

        if args.list:
            sel = b.selectable
            if args.chosen:
                course_list = set(sel.keys())
                chosen = set(ch.keys())
                available = course_list.difference(chosen)
                if available:
                    for k, v in b.selectable.items():
                        if k in available:
                            print(v, end='')
                else:
                    print('No available course.')
            else:
                if sel:
                    for _, v in sel.items():
                        print(v, end='')
                else:
                    print('No course at present.')
        elif args.chosen:
            if ch:
                for _, v in ch.items():
                    print(v, end='')
            else:
                print('No course chosen.')

        if args.drop:
            drop = set(args.drop).intersection(ch.keys())
            for d in drop:
                for _ in range(retry_limit):
                    try:
                        res = b.drop(d)
                        if res:
                            print(f'Successfully dropped {d}.')
                            break
                    except:
                        pass
                    print(f'Failed to drop {d}.' + (' Retrying.' if _ < retry_limit - 1 else ''))

        elist = args.enroll
        amount = 0
        max_ = float('inf') if args.number is None else args.number

        def enroll():
            nonlocal elist, amount
            nonlocal sender, password, receiver, server
            if args.list:
                elist = available_list()
            newlist = []
            if not elist:
                print('No available course.')
            for e in elist:
                res = b.enroll(e)
                if res:
                    print(f'Successfully enrolled in {e}.')
                    if to_send:
                        try:
                            course = b.detail(e)
                            mail_res = buaa.bykc_notice(course, sender, password, receiver, server)
                            if not mail_res: print('Failed to send reminder message.')
                        except:
                            print('Failed to send reminder message.')
                else:
                    newlist.append(e)
                    amount += 1
                    print(f'Enrolling in {e} failed.')
            elist = newlist

        def list_check():
            nonlocal elist, b
            newlist = b.selectable
            new = set(newlist.keys()).difference(elist)
            if not new:
                print('No courses detected.')
                return
            elist.update(new)
            for k in new:
                print(newlist[k], end='')
                if to_send:
                    try:
                        mail_res = buaa.bykc_notice(b.detail(k), sender, password, receiver, server)
                        if not mail_res: print('Failed to send notice.')
                    except:
                        print('Failed to send notice.')

        if args.time is None:
            if not args.list and elist:
                enroll()
        else:
            if args.continuous > 1 and args.list:
                elist = set(b.selectable.keys())
                while True:
                    list_check()
                    time.sleep(args.time)
            else:
                if args.list:
                    elist = available_list()
                while elist or amount >= max_ or args.continuous == 1:
                    enroll()
                    time.sleep(args.time)
                print('Enrolled in all targets')
    except:
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'{e.__class__.__qualname__}: {str(e)}')
