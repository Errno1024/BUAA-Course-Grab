from buaa import bykc
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
parser.add_argument('-d', '--drop', action='extend', default=[], help='The IDs of courses to drop.')
parser.add_argument('-t', '--time', default=None, type=float, help='The interval between tries of enrolling.'
                                                                 'When this option is set, the script will continue trying until all targets are enrolled.')
parser.add_argument('-n', '--number', default=None, type=int, help='The amount of courses to be enrolled.')

def main():
    args = parser.parse_args()

    try:
        vpn = getattr(args, 'vpn', None)

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
            except:
                pass

        elist = args.enroll
        amount = 0
        max_ = float('inf') if args.number is None else args.number

        def enroll():
            nonlocal elist, amount
            if args.list:
                elist = available_list()
            newlist = []
            for e in elist:
                res = b.enroll(e)
                if res:
                    print(f'Successfully enrolled {e}')
                else:
                    newlist.append(e)
                    amount += 1
                    print(f'Enrolling {e} failed')
            elist = newlist

        if args.time is None:
            enroll()
        else:
            if args.list:
                elist = available_list()
            while elist or amount >= max_:
                enroll()
                time.sleep(args.time)
            print('Enrolled all targets')
    except: raise

if __name__ == '__main__':
    main()
