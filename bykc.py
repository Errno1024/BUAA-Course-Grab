from buaa import bykc
import buaa
import argparse
import time
import datetime

TRAVEL_TIME = 10

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
parser.add_argument('-d', '--drop', nargs='*', default=[], metavar='id',
                    help='The IDs of courses to drop.')
parser.add_argument('-t', '--time', default=None, type=float, metavar='interval',
                    help='The interval between tries of enrolling. When this option is set, the script will continue '
                         'trying until all targets are enrolled in.')
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


def main():
    args = parser.parse_args()

    try:
        vpn = getattr(args, 'vpn', None)

        mail = args.mail
        to_send = False
        if mail is not None:
            to_send = True
            sender, password = mail
            server = args.server
            receiver = args.receiver

        b = bykc(args.username, args.password, type=vpn)

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

        if args.list:
            if args.chosen:
                course_list = set(b.selectable.keys())
                chosen = set(b.chosen.keys())
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
            ch = b.chosen
            if ch:
                for _, v in ch.items():
                    print(v, end='')
            else:
                print('No course chosen.')

        for d in args.drop:
            try:
                res = b.drop(d)
                if res:
                    print(f'Successfully dropped {d}')
                else:
                    print(f'Failed to drop {d}')
            except:
                pass

        elist = args.enroll
        amount = 0
        max_ = float('inf') if args.number is None else args.number

        def enroll():
            nonlocal elist, amount
            nonlocal sender, password, receiver, server
            if args.list:
                elist = available_list()
            newlist = []
            for e in elist:
                res = b.enroll(e)
                if res:
                    print(f'Successfully enrolled in {e}')
                    if to_send:
                        e_name = str(e)
                        buaa.remind(e_name, sender, password, receiver, server, title=f'Reminder: BYKC-{e}')
                else:
                    newlist.append(e)
                    amount += 1
                    print(f'Enrolling in {e} failed')
            elist = newlist

        if args.time is None:
            enroll()
        else:
            if args.list:
                elist = available_list()
            while elist or amount >= max_:
                enroll()
                time.sleep(args.time)
            print('Enrolled in all targets')
    except: raise

if __name__ == '__main__':
    try:
        main()
    except Exception as e: print(f'{e.__class__.__qualname__}: {str(e)}')
