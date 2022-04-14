# BUAA Course Grab

*BUAA Course Grab* is intended to be a tool set for BUAA undergraduates to automatically grab or drop courses.

### Hints

- After 2022/03 Boya Subject System update, the system no longer supports selecting forecast courses and drop history courses.
- The API sometimes returns empty selectable course list, which indicates one cannot enroll in any course, and the mechanism is still unknown. When an empty list is returned, ANY attempt to enroll will be rejected, returning status code `1`.

This tool set has following requirements. PIL or cv2 is used to show captcha when required (generally when using VPN).

```
cryptography
requests
PIL // or cv2 + numpy
```

The tool set contains 2 items at present.

### BYKC

`bykc.py` is the Course Grab tool for liberal courses (aka. BYKC). 

To see help, type following commands in your console:

```sh
python bykc.py --help
```

`bykc.py` provides a convenient way to enroll in or drop courses. While `username` refers to your universal identity authentication account and `password` refers to your password, following command shows you the current course list.

```sh
python bykc.py username password -l
```

`bykc.py` also provides a way to show your chosen or not chosen courses. Using switch `-c` to show chosen courses, and to show courses not chosen when `-l` is also passed.

```sh
python bykc.py username password -cl
```

Among arguments, switch `-d` indicates removing courses of following IDs (`course1`, `course2`, ..., `courseN`) simultaneously.

```sh
python bykc.py username password -d course1 course2 ... courseN
```

To enroll in courses, simply attach course IDs after `password`.

```sh
python bykc.py username password course1 course2 ... courseN
```

`bykc.py` provides a way to continuously trying to enroll in a list of courses. By adding `-t` switch to the command line, `bykc.py` switches into recurrent mode, and the interval between two tries can be set. The metric of time is second.

*Notice:* the `-t` switch will be ignored  when `-d` is passed.

```sh
python bykc.py username password course1 course2 ... courseN -t 1
```

To continuously grab all available courses, use `-l` and `-t` simultaneously.

```sh
python bykc.py username password -lt 1
```

If you only want to enroll in a limited number of courses, add `-n` to the command line.

```sh
python bykc.py username password -lt 1 -n 3
```

`bykc.py` can offer a mail reminder service at the time one course is successfully enrolled in. Using `-m` to set the mail address and password of the account. To specify SMTP server and the message receiver, use `-S server` and `-r receiver@xxx.yyy` respectively. If `-r` is not passed, the default receiver is the message sender itself.

```sh
python bykc.py username password -lt 1 -n 3 -m demo@gmail.com demopassword
```

`bykc.py` can select desired campus. Using `-p`, `bykc.py` will ignore courses not in chosen campus. `s` refers to Shahe, and `x` refers to Xueyuanroad.

```sh
python bykc.py username password -lt 1 -n 3 -p x
```

Another switch, `-s`, also controls whether to enroll in a course. Using `-s`, `bykc.py` will never attempt to enroll in a course in conflict with regular course timetable. A time can be specified as default travel time between campuses. The time is `60` by default.

```sh
python bykc.py username password -lt 1 -n 3 -s 60
```

To use VPN, pass `-V` and specify the index of VPN to use.

```sh
python bykc.py usename password -lt 1 -n 3 -V 2
```

Recommended argument combination:

```sh
python bykc.py username password -Clt 1 -s 60 [-V 1 | 2] [-p s | x | sx] [-m demo@gmail.com demopassword]
```

The combination above has identical effect to the following instruction, which uses the default settings.

```sh
python bykc.py username password --default [-V 1 | 2] [-p s | x | sx] [-m demo@gmail.com demopassword]
```

### JWXT

`jwxt.py` is the Course Grab tool for educational administration system (aka. JWXT). 

To see help, type following commands in your console:

```sh
python jwxt.py --help
```

Like `bykc.py`, `jwxt.py` provides a convenient way to enroll in or drop a course. Following command attempts to enroll in a course, where `course` indicates the course ID (e.g.: B3I062410), and `rank` (e.g. 001) indicates the order of course in the system, since there may be a number of courses share the same ID. `rank` is an optional argument.

```sh
python jwxt.py username password course [rank]
```

`-d` switches the execute pattern to removing selected course from your timetable.

```sh
python jwxt.py username password course -d
```

To further locate the target course, `-y` assigns the year when the course is available, and `-s` indicates semester of the course, where 1 refers to the autumn semester, 2 the spring semester and 3 the summer semester.

By default, `-y` and `-s` are assigned with current year and semester respectively.

```sh
python jwxt.py username password course -y 2000 -s 1
```

Like `bykc.py`, `jwxt.py` provides identical way to continuously attempt to enroll in a specific course.

```sh
python jwxt.py username password course -t 1
```

The mail reminder service is identical to `bykc.py`.

```sh
python jwxt.py username password course -t 1 -m demo@gmail.com demopassword
```

`jwxt.py` also provides `-V` to specify VPN.

```sh
python jwxt.py username password course -V 1
```
