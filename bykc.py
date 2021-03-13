from buaa import bykc
import buaa
import argparse
import time
import datetime

TRAVEL_TIME = 60
RETRY_LIMIT = 128

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-h', '--help', action='help', help='To show help.')
parser.add_argument('username', help='The unified identity authentication account.')
parser.add_argument('password', help='Password of the account.')
parser.add_argument('enroll', nargs='*', type=int, default=[], help='The IDs of courses to enroll.')
#parser.add_argument('-V', '--vpn', default=None, type=str, help='The index of VPN used.')
parser.add_argument('-l', '--list', action='store_true',
                    help='To show course list. If this switch is used with -t or --time, the target list will be '
                         'ignored and replaced by course list.')
parser.add_argument('-c', '--chosen', action='store_true',
                    help='To show courses already enrolled in. If this switch is used with -l or --list, courses not '
                         'enrolled in will be showed.')
parser.add_argument('-f', '--forecast', action='store_true',
                    help='To show courses in the forecast list.')
parser.add_argument('-d', '--drop', nargs='*', default=[], metavar='id', type=int,
                    help='The IDs of courses to drop.')
parser.add_argument('-t', '--time', default=None, type=float, metavar='interval',
                    help='The interval between tries of enrolling. When this option is set, the script will continue '
                         'trying until all targets are enrolled in.')
parser.add_argument('-C', '--continuous', action='count',
                    help='If this switch is on, the script will continuously attempt to enroll in courses available. '
                         'If this switch is used twice with -l and -t, the script will automatically output notice '
                         'when new courses become selectable instead of enrolling; if -m is also passed, notice '
                         'messages will be sent.')
parser.add_argument('-n', '--number', default=None, type=int, metavar='amount',
                    help='The amount of courses to be enrolled.')
parser.add_argument('-s', '--safe', nargs='?', default=NotImplemented, type=int, metavar='time',
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

def main():
    args = parser.parse_args()

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

        def available_list():
            nonlocal safety_list, safe_span
            sel = b.selectable
            course_list = set(sel.keys())
            chosen = set(b.chosen.keys())
            res = course_list.difference(chosen)
            if safety_list:
                _res = []
                for c in res:
                    d = sel[c].start
                    dt = sel[c].end - d
                    if buaa.jwxt._schedule_available(d, dt, safety_list, safe_span):
                        _res.append(c)
                return _res
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
            if args.chosen:
                course_list = set(b.selectable.keys())
                chosen = set(ch.keys())
                available = course_list.difference(chosen)
                if available:
                    for k, v in b.selectable.items():
                        if k in available:
                            print(v, end='')
                else:
                    print('No available course.')
            else:
                sel = b.selectable
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
                    except: pass
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
                        e_name = str(e)
                        try:
                            mail_res = buaa.remind(e_name, sender, password, receiver, server, title=f'Reminder: BYKC-{e}')
                            if not mail_res: print('Failed to send reminder message.')
                        except: print('Failed to send reminder message.')
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
            if not args.list:
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
    except: raise

if __name__ == '__main__':
    try:
        main()
    except Exception as e: print(f'{e.__class__.__qualname__}: {str(e)}')
