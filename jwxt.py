from buaa import jwxt
import buaa
import argparse
import time
import re

number_re = re.compile('^([0-9]+)')

RETRY_LIMIT = 3

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-h', '--help', action='help', help='To show help.')
parser.add_argument('username', type=str, help='The unified identity authentication account.')
parser.add_argument('password', type=str, help='Password of the account.')
parser.add_argument('course', type=str, help='The ID of courses to enroll in.')
parser.add_argument('rank', nargs='?', type=str, help='The rank indicates the n-th of courses with the same ID.')
parser.add_argument('-y', '--year', default=None, type=int, help='The current year. The academic year will be '
                                                                 'automatically calculated according to year and '
                                                                 'semester.')
parser.add_argument('-s', '--semester', default=None, type=int, help='The semester. Its value will be restricted '
                                                                     'to 1-3.')
parser.add_argument('-T', '--type', default=None, type=str, help='The course type, which is inferred from course ID if '
                                                                 'not provided. JC for fundamental courses, TS for '
                                                                 'general courses, and ZY for professional courses.')
#parser.add_argument('-V', '--vpn', default=None, type=str, help='The index of VPN used.')
parser.add_argument('-d', '--drop', action='store_true', help='Whether to leave the course.')
parser.add_argument('-t', '--time', default=None, type=float, help='The interval between tries of enrolling. '
                                                                 'When this option is set, the script will continue '
                                                                   'trying until target is enrolled in.')
parser.add_argument('-w', '--wish', default=1, type=int, help='The wish ranking of some course having identical ID '
                                                              'with an amount of courses.')
parser.add_argument('-W', '--weight', default=100, type=int, help='The weight of sport course, which will be '
                                                                  'automatically restricted to 1-100.')
parser.add_argument('-m', '--mail', nargs=2, default=None, type=str, metavar=('account', 'password'), help='The mail '
                                                                    'account applied to send reminder email. Setting '
                                                                    'an email address indicates sending a reminder '
                                                                    'when target course is successfully enrolled in.')
parser.add_argument('-S', '--server', type=str, default=None, help='The SMTP server of the mail system. Automatically '
                                                                   'inferred if not given.')
parser.add_argument('-r', '--receiver', type=str, default=None, help='The receiver of the reminder. The reminder will '
                                                                     'be sent to the sender account if not given.')
parser.add_argument('-R', '--retry', type=int, default=RETRY_LIMIT, help='The retry limit. The script will '
                                                                         'automatically retry when connection is '
                                                                         'aborted by server. The default retry limit '
                                                                         f'is {RETRY_LIMIT}.')

def main():
    args = parser.parse_args()

    try:
        vpn = getattr(args, 'vpn', None)

        j = jwxt(args.username, args.password, type=vpn)
        t = time.localtime()

        retry_count = 0
        retry_limit = max(args.retry, 0)

        course = args.course.upper()
        semester = args.semester
        if semester is not None:
            semester = min(max(args.semester, 1), 3)
        else:
            semester = 2 if t.tm_mon < 6 else (3 if t.tm_mon < 8 else 1)

        year = args.year
        if year is None:
            year = t.tm_year

        typ = args.type
        if not typ in ('JC', 'TS', 'ZY'):
            typ = jwxt.course_type(course[2])

        rank = args.rank
        if rank is None:
            rank = '001'
        else:
            rank_int = re.search(number_re, rank)
            if rank_int == None:
                rank = '001-' + rank
            else:
                rank = ('0' * max(0, 3 - len(rank_int.group(1)))) + rank

        wish = max(1, args.wish)
        weight = max(min(args.weight, 100), 1)

        mail = args.mail
        to_send = False
        if mail is not None:
            to_send = True
            sender, password = mail
            server = args.server
            receiver = args.receiver

        def enroll():
            nonlocal year, semester, course, typ, rank, wish, weight
            nonlocal sender, password, receiver, server
            res = False
            while retry_count <= retry_limit:
                try:
                    res = j.choose(year, semester, course, typ, rank, wish=wish, weight=weight, verbose=True)
                except Exception as e:
                    if retry_count < retry_limit:
                        print(f'{e.__class__.__qualname__}: {str(e)}')
                    else: raise
                else: break
            if res and to_send:
                buaa.remind(course, sender, password, receiver, server, title=f'Reminder: {course}')
            return res

        def drop():
            nonlocal year, semester, course, typ, rank, wish, weight
            return j.drop(year, semester, course, typ)

        if args.drop:
            if drop():
                print(f'Successfully dropped {course}')
            else:
                print(f'Dropping {course} failed')
        else:
            if args.time is None:
                if enroll():
                    print(f'Successfully enrolled in {course}')
                else:
                    print(f'Enrolling in {course} failed')
            else:
                count = 0
                while not enroll():
                    count += 1
                    print(f'{count}: Enrolling in {course} failed')
                    time.sleep(args.time)
                print(f'Successfully enrolled in {course}')
    except: raise

if __name__ == '__main__':
    try:
        main()
    except Exception as e: print(f'{e.__class__.__qualname__}: {str(e)}')

