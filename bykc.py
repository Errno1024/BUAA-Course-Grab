from buaa import bykc
import buaa
import argparse
import time

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-h', '--help', action='help', help='To show help.')
parser.add_argument('username', help='The unified identity authentication account.')
parser.add_argument('password', help='Password of the account.')
parser.add_argument('enroll', nargs='*', type=int, default=[], help='The IDs of courses to enroll.')
#parser.add_argument('-V', '--vpn', default=None, type=str, help='The index of VPN used.')
parser.add_argument('-l', '--list', action='store_true', help='To show course list. If this switch is used '
                                                              'with -t or --time, the enroll list will be ignored and replaced by course list.')
parser.add_argument('-d', '--drop', nargs='*', default=[], help='The IDs of courses to drop.')
parser.add_argument('-t', '--time', default=None, type=float, help='The interval between tries of enrolling.'
                                                                 'When this option is set, the script will continue trying until all targets are enrolled.')
parser.add_argument('-n', '--number', default=None, type=int, help='The amount of courses to be enrolled.')
parser.add_argument('-m', '--mail', nargs=2, default=None, type=str, metavar=('account', 'password'), help='The mail '
                                                                    'account applied to send reminder email. Setting '
                                                                    'an email address indicates sending a reminder '
                                                                    'when a target course is successfully enrolled in.')
parser.add_argument('-S', '--server', type=str, default=None, help='The SMTP server of the mail system. Automatically '
                                                                   'inferred if not given.')
parser.add_argument('-r', '--receiver', type=str, default=None, help='The receiver of the reminder. The reminder will '
                                                                     'be sent to the sender account if not given.')

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
        if args.list:
            for _, v in b.selectable.items():
                print(v, end='')

        def available_list():
            course_list = set(b.selectable.keys())
            chosen = set(b.chosen.keys())
            return list(course_list.difference(chosen))

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
