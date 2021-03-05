import requests
import re
import urllib3
import json
import time
import datetime


def date(s):
    return datetime.datetime(*time.strptime(s, "%Y-%m-%d %H:%M:%S")[:6])


def date2str(d):
    return d.strftime("%Y-%m-%d %H:%M:%S")


def url_escape(url):
    ESCAPE = [
        (' ', '%20'),
        ('"', '%22'),
        ('#', '%23'),
        ('%', '%25'),
        ('&', '%26'),
        ('(', '%28'),
        (')', '%29'),
        ('+', '%2B'),
        (',', '%2C'),
        ('/', '%2F'),
        (':', '%3A'),
        (';', '%3B'),
        ('<', '%3C'),
        ('=', '%3D'),
        ('>', '%3E'),
        ('?', '%3F'),
        ('@', '%40'),
        ('\\', '%5C'),
        ('|', '%7C'),
    ]
    for k, v in ESCAPE:
        url = url.replace(k, v)
    return url


def params(url):
    parsed = urllib3.util.parse_url(url).query
    res = {}
    for s in parsed.split('&'):
        s = s.split('=')
        v = ''
        if len(s) > 1:
            v = s[1]
        res[s[0]] = v
    return res


class CASTGC:
    def __init__(self, username, password, type=None, refresh=False):
        self.username = username
        self.password = password
        self.type = type
        if refresh:
            self.refresh()

    def refresh(self):
        login_url = 'https://sso.buaa.edu.cn/login'
        if self.type is not None:
            login_url = f'https://sso-443.e{self.type}.buaa.edu.cn/login'
        execution_re = re.compile(r'name="execution" value="([^"]*)"')
        headers = {
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3100.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        res = requests.get(login_url, headers=headers)
        _cookies = res.cookies
        content = res.content.decode('utf8')
        execution = re.search(execution_re, content).group(1)

        data = {
            'username': self.username,
            'password': self.password,
            'type': 'username_password',
            'execution': execution,
            '_eventId': 'submit',
        }

        ck = '; '.join(map(lambda x: f"{x[0]}={x[1]}", _cookies.get_dict().items()))
        res = requests.post(login_url, data=data, headers={
            'Cookie': ck,
            **headers,
        }, files=[], allow_redirects=False)
        _CASTGC = res.cookies.get('CASTGC')
        self.token = _CASTGC
        self.execution = execution
        self.login_url = login_url
        self.headers = headers
        self.data = data


class login:
    def __init__(self, url, token):
        self.token = token
        self.refresh(url)

    def refresh(self, url):
        token = self.token
        token.refresh()
        url = token.login_url + f"?TARGET={url_escape(url)}"
        res = requests.post(
            url,
            data=token.data,
            cookies={'CASTGC': token.token},
            headers={
                **token.headers,
            },
            files=[],
        )
        cookies = {}
        for his in res.history[1:]:
            cookies.update(his.cookies.get_dict())
        self.url = res.url
        self.cookies = cookies
        self.session = cookies.get('JSESSIONID', None)

    def post(self, *args, cookies={}, headers={}, **kwargs):
        return requests.post(*args, cookies={**cookies, **self.cookies}, headers={**headers, **self.headers}, **kwargs)

    def get(self, *args, cookies={}, headers={}, **kwargs):
        return requests.get(*args, cookies={**cookies, **self.cookies}, headers={**headers, **self.headers},
                            **kwargs)

    @property
    def headers(self):
        return self.token.headers


class bykc(login):
    class course:
        def __init__(self, data):
            self.id = data['id']
            self.data = data
            self.campus = json.loads(data['courseCampus'])
            self.college = data['courseCollege']
            self.provider = data['courseContact']
            self.current = data['courseCurrentCount']
            self.max = data['courseMaxCount']
            self.name = data['courseName']
            self.teacher = data['courseTeacher']
            self.select_start = date(data['courseSelectStartDate'])
            self.select_end = date(data['courseSelectEndDate'])
            self.start = date(data['courseStartDate'])
            self.end = date(data['courseEndDate'])
            self.classroom = data['coursePosition']

        def __str__(self):
            return \
                f"{self.id} {self.name} {self.teacher}\n" \
                    f"{self.classroom} {self.college} {self.current if self.current is not None else '-'}/{self.max}\n" \
                    f"Start:  {date2str(self.start)}\n" \
                    f"End:    {date2str(self.end)}\n" \
                    f"Enroll: {date2str(self.select_start)} - {date2str(self.select_end)}\n" \
                    ""

        def __repr__(self):
            return str(self)

    @property
    def weburl(self):
        if self.token and self.token.type is not None:
            return f'https://bykc.e{self.token.type}.buaa.edu.cn'
        return 'http://bykc.buaa.edu.cn'

    @property
    def loginurl(self):
        return f'{self.weburl}/sscv/casLogin'

    def __init__(self, *args, **kwargs):
        self.token = CASTGC(*args, **kwargs)
        super().__init__(self.loginurl, self.token)
        self.bykc_token = params(self.url)['token']

    def refresh(self, url=None):
        super().refresh(self.loginurl)

    @property
    def headers(self):
        return {'auth_token': self.bykc_token, **super().headers}

    def query(self, name):
        try:
            return json.loads(self.get(f'{self.weburl}/sscv/{name}').content).get('data', [])
        except:
            self.refresh()
        return json.loads(self.get(f'{self.weburl}/sscv/{name}').content).get('data', [])

    def api(self, name, payload={}):
        try:
            return json.loads(self.post(
                f'{self.weburl}/sscv/{name}',
                data=json.dumps(payload, ensure_ascii=True),
                headers={'Content-Type': 'application/json;charset=UTF-8'},
            ).content,
                              ).get('data', None)
        except:
            self.refresh()
        return json.loads(self.post(
            f'{self.weburl}/sscv/{name}',
            data=json.dumps(payload, ensure_ascii=True),
            headers={'Content-Type': 'application/json;charset=UTF-8'},
        ).content,
                          ).get('data', None)

    def courses(self, data):
        res = {}
        for c in data:
            res[c['id']] = self.course(c)
        return res

    @property
    def fore(self):
        res = self.query('queryForeCourse')
        return self.courses(res)

    @property
    def selectable(self):
        res = self.query('querySelectableCourse')
        return self.courses(res)

    @property
    def history(self):
        res = self.query('queryChosenCourse').get('historyCourseList', [])
        _res = []
        for c in res:
            cc = c.get('courseInfo', None)
            if cc is not None:
                _res.append(cc)
        return self.courses(_res)

    @property
    def chosen(self):
        res = self.query('queryChosenCourse').get('courseList', [])
        _res = []
        for c in res:
            cc = c.get('courseInfo', None)
            if cc is not None:
                _res.append(cc)
        return self.courses(_res)

    def detail(self, id):
        res = self.api('queryCourseById', {'id': id})
        if res is None:
            return None
        return self.course(res)

    def enroll(self, id):
        res = self.api('choseCourse', {'courseId': id})
        return res is not None

    def drop(self, id):
        res = self.api('delChosenCourse', {'id': id})
        return res is not None


class jwxt(login):
    @classmethod
    def course_type(cls, label):
        label = label.upper()
        if label in 'ABCD':
            return 'JC'
        elif label in 'EFGH':
            return 'TS'
        return 'ZY'

    @property
    def weburl(self):
        if self.token and self.token.type is not None:
            return f'https://jwxt-7001.e{self.token.type}.buaa.edu.cn'
        return 'http://jwxt.buaa.edu.cn:7001'

    @property
    def loginurl(self):
        return f'{self.weburl}/{self.path_id}/welcome?falg=1'

    @property
    def path_id(self):
        return 'ieas2.1'

    def __init__(self, *args, **kwargs):
        self.token = CASTGC(*args, **kwargs)
        super().__init__(self.loginurl, self.token)
        self.__token_re = re.compile('<input type="hidden" id="token" name="token" value="([0-9\.]*)" />')

    def refresh(self, url=None):
        super().refresh(self.loginurl)

    def choose(self, year, season, course_id: str, course_type='ZY', tail='001', *, external=False, wish=None, weight=None, verbose=False):
        if len(course_id) < 9 or len(course_id) > 10:
            raise (Exception)
        course_id = course_id.upper()
        pageXkmkdm = course_type + 'L'
        if pageXkmkdm not in ('JCL', 'TSL', 'ZYL'):
            raise Exception
        course_type = course_id[2]
        if pageXkmkdm == 'ZYL' and course_type not in 'IJ':
            course_type = 'J'
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        cid = f"{head}-{season}-{course_id}-{tail}"

        data = {
            'token': '',
            'pageXklb': 'xslbxk',
            'pageKclb': course_type,
            'rwh': '',
            'path_id': self.path_id,
            'zy': '',
            'qz': '',
            'kcdmpx': '',
            'kcmcpx': '',
            'rlpx': '',
            'pageKkxiaoqu': '',
            'pageKkyx': '',
            'pageKcmc': course_id,
            'pageXnxq': f'{head}{season}',
            'pageXkmkdm': pageXkmkdm,
        }
        payload = '&'.join(map(lambda x: f"{url_escape(x[0])}={url_escape(x[1])}", data.items()))
        headers = {
            'Referrer': f'{self.weburl}/{self.path_id}/xslbxk/queryXsxkList',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Origin': self.weburl,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        if wish is not None:
            data['zy'] = str(wish)
        if weight is not None:
            data['qz'] = str(min(max(weight, 0), 100))

        places_re = f'<input id="xkyq_{cid}" type="hidden" value=""/>\\s*([0-9]+)/([0-9]+)[^0-9]+?([0-9]+)/([0-9]+)'
        places_re = re.compile(places_re)

        choice_token = None
        while choice_token is None:
            form = self.post(f'{self.weburl}/{self.path_id}/xslbxk/queryXsxkList', data=payload,
                             headers=headers).content.decode('utf8')

            if form.find('</form>') < 0:
                if verbose:
                    print('Refreshing cookies.')
                self.refresh()
                continue

            places = re.search(places_re, form)
            if places is None:
                return self.enrolled(year, season, course_id, tail)
            if external:
                rest = int(places.group(4)) - int(places.group(3))
            else:
                rest = int(places.group(2)) - int(places.group(1))
            if rest <= 0:
                return False

            choice_token = re.search(self.__token_re, form)
            if choice_token is not None:
                choice_token = choice_token.group(1)
            elif verbose:
                print('Failed to get access token. Retrying.')
        data['token'] = choice_token
        data['rwh'] = cid
        payload1 = '&'.join(map(lambda x: f"{url_escape(x[0])}={url_escape(x[1])}", data.items()))
        self.post(f'{self.weburl}/{self.path_id}/xslbxk/saveXsxk', data=payload1, headers=headers)

        return self.enrolled(year, season, course_id, tail)

    def drop(self, year, season, course_id: str, tail='001'):
        if len(course_id) < 9 or len(course_id) > 10:
            raise (Exception)
        course_id = course_id.upper()
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        cid = f"{head}-{season}-{course_id}-{tail}"

        data = {
            'rwh': cid,
            'pageXklb': 'xslbxk',
            'pageXnxq': f'{head}{season}',
            'pageKcmc': course_id,
        }
        payload = '&'.join(map(lambda x: f"{url_escape(x[0])}={url_escape(x[1])}", data.items()))
        headers = {
            'Referrer': f'{self.weburl}/{self.path_id}/xslbxk/queryYxkc?pageXklb=xslbxk&pageXnxq={head}{season}',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Origin': self.weburl,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        self.post(f'{self.weburl}/{self.path_id}/xslbxk/saveXstk', data=payload, headers=headers)

        return not self.enrolled(year, season, course_id, tail)

    def enrolled(self, year, season, course_id: str, tail='001'):
        if len(course_id) < 9 or len(course_id) > 10:
            raise (Exception)
        course_id = course_id.upper()
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        cid = f"{head}-{season}-{course_id}-{tail}"

        data = {
            'rwh': '',
            'pageXklb': 'xslbxk',
            'pageXnxq': f'{head}{season}',
            'pageKcmc': course_id,
        }
        headers = {
            'Referrer': f'{self.weburl}/{self.path_id}/xslbxk/queryYxkc?pageXklb=xslbxk&pageXnxq={head}{season}',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Origin': self.weburl,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        payload = '&'.join(map(lambda x: f"{url_escape(x[0])}={url_escape(x[1])}", data.items()))
        form = self.post(f'{self.weburl}/{self.path_id}/xslbxk/queryYxkc', data=payload,
                         headers=headers).content.decode('utf8')
        return form.find(f'id="{cid}"') >= 0

