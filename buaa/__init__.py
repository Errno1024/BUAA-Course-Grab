import requests
import re
import json
import time
import datetime
import smtp

from . import bykc_encrypt

try:
    import _thread as thread
except:
    import thread

try:
    import cv2
    import numpy as np

    def show_image(stream, title=None):
        img = cv2.imdecode(np.frombuffer(stream, np.uint8), cv2.IMREAD_ANYCOLOR)
        cv2.imshow('' if title is None else title, img)
        while cv2.waitKey(0) != -1: pass
except ModuleNotFoundError:
    from PIL import Image
    import io

    def show_image(stream, title=None):
        img = Image.open(io.BytesIO(stream))
        img.show()

from . import urllib3

class BUAAException(Exception):
    def __init__(self, *args, status=None):
        super().__init__(*args)
        self.status = status

def _binary_search(v, lst, key=None):
    if not lst: return 0
    if key is None: key = lambda x: x
    l, r = 0, len(lst)
    while l < r:
        m = (l + r) // 2
        if key(lst[m]) < v:
            l = m + 1
        else:
            r = m
    return l

PRODUCT_NAME = 'BUAA Course Grab'

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
    parsed = urllib3.parse_url(url).query
    if parsed is None:
        return {}
    res = {}
    for s in parsed.split('&'):
        s = s.split('=')
        v = ''
        if len(s) > 1:
            v = s[1]
        res[s[0]] = v
    return res

class CASTGC:
    re_cas_captcha_id = re.compile(r"config.captcha\s*=\s*{\s*type:\s*'image',\s*id:\s*'(-?[0-9]+)'")
    re_webvpn_csrf_token = re.compile(r'<meta\s*name="csrf-token"\s*content="([A-Za-z0-9/=+-]+)"')
    re_execution = re.compile(r'name="execution" value="([^"]*)"')
    headers = {
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3100.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    def __init__(self, username, password, type=None, refresh=False):
        self.username = username
        self.password = password
        self.type = type
        if refresh:
            self.refresh()

    @property
    def vpn(self):
        return self.type is not None

    @property
    def vpn_login_url(self):
        if self.type is None:
            return None
        return f'https://e{self.type}.buaa.edu.cn/users/sign_in'

    @property
    def base_url(self):
        if self.type is not None:
            return f'https://sso-443.e{self.type}.buaa.edu.cn'
        return 'https://sso.buaa.edu.cn'

    @property
    def login_url(self):
        return f'{self.base_url}/login'

    @property
    def captcha_url(self):
        return f'{self.base_url}/captcha?captchaId='

    @property
    def app_url(self):
        return 'https://app.buaa.edu.cn/uc/wap/login'

    def refresh_webvpn(self):
        if not self.vpn:
            return
        login_url = self.vpn_login_url
        res = requests.get(login_url, headers=self.headers)
        _cookies = res.cookies
        content = res.content.decode('utf8')
        csrf_token = re.search(self.re_webvpn_csrf_token, content).group(1)

        data = {
            'utf8': "✓",
            'user[login]': self.username,
            'user[password]': self.password,
            'user[dymatice_code]': 'unknown',
            'user[otp_with_capcha]': 'false',
            'authenticity_token': csrf_token,
        }

        ck = '; '.join(map(lambda x: f"{x[0]}={x[1]}", _cookies.get_dict().items()))
        res = requests.post(login_url, data=data, headers={
            'Cookie': ck,
            **self.headers,
        }, files=[])
        self.vpn_cookies = {}
        for r in res.history:
            self.vpn_cookies.update(r.cookies.get_dict())

    def refresh_app(self):
        data = {
            'username': self.username,
            'password': self.password,
        }
        res = requests.post(f'{self.app_url}/check', data=data, headers=self.headers)
        res_data = json.loads(res.content.decode('utf8'))
        suc = res_data['e'] == 0
        if not suc:
            raise BUAAException(f'Login error: {res_data.get("m", "Unknown Error")}')
        self.app_cookies = res.cookies.get_dict()

    def refresh(self):
        login_url = self.login_url
        captcha_url = self.captcha_url

        headers = self.headers

        res = requests.get(login_url, headers=headers)
        _cookies = res.cookies
        content = res.content.decode('utf8')
        execution = re.search(self.re_execution, content).group(1)

        data = {
            'username': self.username,
            'password': self.password,
            'type': 'username_password',
            'execution': execution,
            '_eventId': 'submit',
        }

        ck = '; '.join(map(lambda x: f"{x[0]}={x[1]}", _cookies.get_dict().items()))

        _CASTGC = None
        while _CASTGC is None:
            captcha_id = re.search(self.re_cas_captcha_id, content)
            if captcha_id is not None:
                captcha_id = captcha_id.group(1)
                captcha_pic = requests.get(f'{captcha_url}{captcha_id}', headers={
                    'Cookie': ck,
                    **headers,
                }).content
                thread.start_new(show_image, (captcha_pic, 'Captcha'))

                captcha_answer = input('Input captcha: ')
                data['captcha'] = captcha_answer

            res = requests.post(login_url, data=data, headers={
                'Cookie': ck,
                **headers,
            }, files=[], allow_redirects=False)
            _CASTGC = res.cookies.get('CASTGC')

            if _CASTGC is None:
                # TODO: Sometimes CAS will refuse all attempts even if refreshed,
                #       and the cause is still unclear.
                raise BUAAException('Connection refused, please retry after a few seconds. '
                                    'Please note that account with a weak password might be '
                                    'forbidden to access sso.buaa.edu.cn.')

        self.token = _CASTGC
        self.execution = execution
        self.data = data

        self.vpn_cookies = {}
        self.refresh_webvpn()

        self.app_cookies = {}
        #self.refresh_app()

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
            cookies={
                'CASTGC': token.token,
                **token.vpn_cookies,
            },
            headers={
                **token.headers,
            },
            files=[],
        )
        cookies = {**token.vpn_cookies, **token.app_cookies}
        for his in res.history[1:]:
            cookies.update(his.cookies.get_dict())
        self.url = res.url
        self.cookies = cookies
        self.session = cookies.get('JSESSIONID', None)

    def post(self, *args, cookies=None, headers=None, **kwargs):
        if headers is None:
            headers = {}
        if cookies is None:
            cookies = {}
        return requests.post(*args, cookies={**cookies, **self.cookies}, headers={**headers, **self.headers}, **kwargs)

    def get(self, *args, cookies=None, headers=None, **kwargs):
        if headers is None:
            headers = {}
        if cookies is None:
            cookies = {}
        return requests.get(*args, cookies={**cookies, **self.cookies}, headers={**headers, **self.headers},
                            **kwargs)

    @property
    def headers(self):
        return self.token.headers


course_time_re = re.compile(r'\[([0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)(?:周)?\]'
                            r'(?:星期)?(一|二|三|四|五|六|日|[0-9])第([0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)')

college_calendar_month_re = re.compile(
    r'<div\s+class="xfyq_top">[0-9]+年([0-9]+)月</div>'
)

college_calendar_day_re = re.compile(
    r'<td\s+align="center"\s+class="sk_gray">1</td>\s*'
    r'<td\s+align="center"\s+class="sk_green">\s*([0-9]+)'
)

timetable_re = re.compile(
    r'<tr (?:class="[A-Za-z0-9- ]+")?>\s*' + \
    r'<td[^>]*>[\S\s]*?</td>\s*' * 2 + \
    r'<td[^>]*>([\S\s]*?)</td>\s*' * 7 + \
    r'</tr>'
)

timespan_re = r'(?:[0-9]+(?:-[0-9]+)?(?:[,，][0-9]+(?:-[0-9]+)?)*)'
timespan_grouped_re = r'([0-9]+(?:-[0-9]+)?(?:[,，][0-9]+(?:-[0-9]+)?)*)'
timespan_single_re = r'([0-9]+)(?:-([0-9]+))?'

week_single_re = rf'(?:[^\]]*\[{timespan_re}\]周?)'
week_single_grouped_re = re.compile(rf'^(?:([^\]]*)\[{timespan_grouped_re}\]周?)')

week_re = rf'(?:{week_single_re}(?:[,，]{week_single_re})*)'
week_grouped_re = rf'({week_single_re}(?:[,，]{week_single_re})*)'

timetable_item_re = rf'{week_re}[\S\s]*?第{timespan_re}节'
timetable_item_grouped_re = rf'{week_grouped_re}(?:</br>)?([\S\s]*?)\s*第{timespan_grouped_re}节'

timetable_all_re = re.compile(
    r'([^<]*)\s*'
    r'</br>\s*' + \
    rf'({timetable_item_re}(?:[,，]{timetable_item_re})*)'
)

class bykc(login):
    class course:
        RE_POS_SHAHE = r'(?:(?:J|S|教|实|实验楼)[0-5]|沙河|咏曼)'
        RE_POS_XUEYUANROAD = r'(?:[A-H][0-9]{3,4}|学院路|学术交流厅|主|[(（][1-5一二三四五][)）]|^体育场)'

        def __init__(self, data):
            self.id = data['id']
            self.data = data
            try:
                self.campus = json.loads(data['courseCampus'])
            except:
                self.campus = [data['courseCampus']]
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
            self.desc = data.get('courseDesc', None)

        @property
        def position(self):
            if re.search(self.RE_POS_SHAHE, self.classroom):
                return 's'
            if re.search(self.RE_POS_XUEYUANROAD, self.classroom):
                return 'x'
            return 'x'

        def __str__(self):
            return \
                f"{self.id} {self.name} {self.teacher}\n" \
                    f"{self.classroom} {self.college} {self.current if self.current is not None else '-'}/{self.max}\n" \
                    f"Start:  {date2str(self.start)}\n" \
                    f"End:    {date2str(self.end)}\n" \
                    f"Enroll: {date2str(self.select_start)} - {date2str(self.select_end)}\n" \
                    f""

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

    def __init__(self, *args, retry_limit=16, **kwargs):
        self.token = CASTGC(*args, **kwargs)
        self.retry_limit = retry_limit
        super().__init__(self.loginurl, self.token)
        self.bykc_token = params(self.url)
        while self.bykc_token is None:
            self.refresh()
        self.bykc_token = self.bykc_token.get('token', None)

    def refresh(self, url=None):
        super().refresh(self.loginurl)

    @property
    def headers(self):
        return {'auth_token': self.bykc_token, **super().headers}

    def query(self, name, default=None, throw=False):
        if default is None: default = []
        try:
            res = self.__encrypted_api(name)
            if res is None:
                res = default
            return res
        except:
            self.refresh()
        try:
            res = self.__encrypted_api(name)
        except:
            if throw:
                raise
            res = None
        if res is None:
            res = default
        return res

    def __encrypted_api(self, name, payload=None):
        if payload is None:
            payload = {}

        raw_data = json.dumps(payload)
        #raw_data = json.dumps(payload, ensure_ascii=True)

        raw_data_bytes = raw_data.encode('utf8')
        aes_key = bykc_encrypt.generate_aes_key()
        data_sign = bykc_encrypt.sign(raw_data_bytes)
        timestamp = int(time.time() * 1000)
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'ak': bykc_encrypt.rsa_encrypt(aes_key).decode('utf8'),
            'sk': bykc_encrypt.rsa_encrypt(data_sign).decode('utf8'),
            'ts': str(timestamp),
        }

        encrypted_data = bykc_encrypt.b64encode(bykc_encrypt.aes_encrypt(raw_data_bytes, aes_key))
        res = self.post(
            f'{self.weburl}/sscv/{name}',
            data=encrypted_data,
            headers=headers,
        )
        if res.status_code < 200 or res.status_code >= 300:
            raise BUAAException(f'API {name} returns error status code {res.status_code} with content: {res.content}')

        content = res.content
        try:
            content = bykc_encrypt.b64decode(content)
        except ValueError:
            # The response is not base64 format, which indicates the content is raw text with error status code
            res_decode = json.loads(content)
            status = res_decode.get('status', None)
            raise BUAAException(f'API {name} returns error status {status} with data {res_decode.get("data", None)}', status=status)
        try:
            res_decode = json.loads(bykc_encrypt.aes_decrypt(content, aes_key))
        except ValueError:
            raise BUAAException(f'API {name} returns invalid data {content}')
        status = res_decode.get('status', None)
        if status != '0':
            raise BUAAException(f'API {name} returns error status {status} with data {res_decode.get("data", None)}', status=status)
        return res_decode.get('data', None)

    def api(self, name, payload=None):
        if payload is None: payload = {}
        try:
            return self.__encrypted_api(name=name, payload=payload)
        except:
            self.refresh()
        return self.__encrypted_api(name=name, payload=payload)

    def courses(self, data):
        res = {}
        for c in data:
            res[c['id']] = self.course(c)
        return res

    @property
    def forecast(self):
        res = None
        for _ in range(self.retry_limit + 1):
            res = self.query('queryForeCourse', None)
            if res is not None: break
        if res is None: raise BUAAException('Failed to get forecast')
        return self.courses(res)

    @property
    def selectable(self):
        res = None
        for _ in range(self.retry_limit + 1):
            res = self.query('querySelectableCourse', None)
            if res is not None: break
        if res is None: raise BUAAException('Failed to get selectable course list')
        return self.courses(res)

    @property
    def history(self):
        res = None
        for _ in range(self.retry_limit + 1):
            res = self.query('queryChosenCourse', None)
            if res is None or not isinstance(res, dict): self.refresh()
            else: break
        if res is None or not isinstance(res, dict): raise BUAAException('Failed to get history')
        res = res.get('historyCourseList', [])
        _res = []
        for c in res:
            cc = c.get('courseInfo', None)
            if cc is not None:
                _res.append(cc)
        return self.courses(_res)

    @property
    def chosen(self):
        res = None
        for _ in range(self.retry_limit + 1):
            res = self.query('queryChosenCourse', None)
            if res is None or not isinstance(res, dict): self.refresh()
            else: break
        if res is None or not isinstance(res, dict): raise BUAAException('Failed to get chosen courses')
        res = res.get('courseList', [])
        _res = []
        for c in res:
            cc = c.get('courseInfo', None)
            if cc is not None:
                _res.append(cc)
        return self.courses(_res)

    def detail(self, id, throw=False):
        res = None
        for _ in range(self.retry_limit + 1):
            try:
                res = self.api('queryCourseById', {'id': id})
            except BUAAException as e:
                res = None
                if e.status == '1':
                    break
                if throw:
                    raise
            if res is not None: break
        if res is None: raise BUAAException('Failed to get course detail')
        return self.course(res)

    def enroll(self, id, throw=False):
        try:
            res = self.api('choseCourse', {'courseId': id})
        except:
            if throw:
                raise
            res = None
        if res is None: return False
        return id in self.chosen

    def drop(self, id, throw=False):
        try:
            res = self.api('delChosenCourse', {'id': id})
        except:
            if throw:
                raise
            res = None
        if res is None: return False
        return id not in self.chosen


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
            return f'https://jwxt-8080.e{self.token.type}.buaa.edu.cn'
        return 'http://jwxt.buaa.edu.cn:8080'

    @property
    def loginurl(self):
        return f'{self.weburl}/{self.path_id}/welcome?falg=1'

    @property
    def path_id(self):
        return 'ieas2.1'

    def __init__(self, *args, **kwargs):
        self.token = CASTGC(*args, **kwargs)
        super().__init__(self.loginurl, self.token)
        self.__token_re = re.compile('<input type="hidden" id="token" name="token" value="([0-9.]*)" />')

    def refresh(self, url=None):
        super().refresh(self.loginurl)

    def choose(self, year, season, course_id: str, course_type='ZY', tail='001', *, external=False, wish=None, weight=None, verbose=False):
        if len(course_id) < 9 or len(course_id) > 10:
            raise BUAAException('Invalid course ID')
        course_id = course_id.upper()
        pageXkmkdm = course_type + 'L'
        if pageXkmkdm not in ('JCL', 'TSL', 'ZYL'):
            raise BUAAException('Invalid course type')
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
            raise BUAAException('Invalid course ID')
        course_id = course_id.upper()
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        cid = f"{head}-{season}-{course_id}-{tail}"

        data = {
            'rwh': cid,
            'pageXklb': 'xslbxk',
            'pageXnxq': f'{head}{season}',
            'pageKcmc': course_id,
            'pageNj': '',
            'pageYxdm': '',
            'pageZydm': '',
            'pageBs': '',
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
            raise BUAAException('Invalid course ID')
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

    def export_timetable(self, year, season, file: str=None):
        attachment_re = re.compile(r'^attachment;\s+filename="([^"]*)"$')

        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        url = f'{self.weburl}/{self.path_id}/kbcx/ExportGrKbxx?xnxq={head}{season}'
        res = self.get(url)
        cd = res.headers.get('Content-Disposition', '')
        cd = re.match(attachment_re, cd)
        if cd is not None:
            if file:
                filename = file
            else:
                filename = cd.group(1).encode('iso-8859-1').decode('gbk')
            with open(filename, 'wb') as f:
                f.write(res.content)
            return filename
        return None

    def first_day(self, year, season):
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        url = f'{self.weburl}/{self.path_id}/xlcx/queryXlcx?xnxq={head}{season}'
        res = self.get(url)
        m = re.search(college_calendar_month_re, res.text)
        if m is None:
            return None
        month = int(m.group(1))
        d = re.search(college_calendar_day_re, res.text)
        if d is None:
            return None
        day = int(d.group(1))
        return datetime.datetime(year=year, month=month, day=day)

    class course_time:
        def __init__(self, name, teacher, date):
            self.name = name
            self.teacher = teacher
            self.date = date

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.name == other.name and \
                    self.teacher == other.teacher and \
                    self.date == other.date
            return NotImplemented

        def __lt__(self, other):
            if isinstance(other, self.__class__):
                return self.date < other.date
            elif isinstance(other, datetime.datetime):
                return self.date < other
            return NotImplemented

        def __str__(self):
            return f'{self.name} {self.teacher} {date2str(self.date)} - {date2str(self.date + COURSE_SPAN)}'

        def __repr__(self):
            return str(self)

    def timetable(self, year, season):
        _season = min(season, 2)
        head = '%04d-%04d' % (year - _season + 1, year - _season + 2)
        schedules = []
        url = f'{self.weburl}/{self.path_id}/kbcx/queryGrkb?xnxq={head}{season}'
        while True:
            res = self.get(url).text
            tables = re.findall(timetable_re, res)
            tables = list(zip(*tables))
            first_day = self.first_day(year, season)
            if len(tables) == 7 and first_day:
                break
            self.refresh()
        for i in range(7):
            table = tables[i]
            for item_raw in table:
                if item_raw == '&nbsp': continue
                item = re.search(timetable_all_re, item_raw)
                if item is None: continue
                course_name, schedule = item.groups()
                m = re.search(timetable_item_grouped_re, schedule)
                while m is not None:
                    schedule = schedule[m.end() + 1:]
                    teacher_weeks, classroom, tspan = m.groups()
                    teacher_weeks = _teacher_weeks(teacher_weeks)
                    tspan = timespan(tspan)
                    tspan = list(map(time_lut, tspan))
                    for teacher, weeks in teacher_weeks:
                        for w in timespan(weeks):
                            for t in tspan:
                                date = first_day + datetime.timedelta(days=(w - 1) * 7 + i) + t
                                schedules.append(self.course_time(
                                    course_name,
                                    teacher,
                                    date,
                                ))
                    m = re.search(timetable_item_grouped_re, schedule)
        return sorted(schedules)

    @classmethod
    def semester_infer(cls, month=time.localtime().tm_mon):
        return 2 if month < 6 else (3 if month < 8 else 1)

    @classmethod
    def _schedule_available(cls, t, tspan, schedule_list, span=datetime.timedelta()):
        pos = _binary_search(t, schedule_list)
        if pos > 0:
            left = schedule_list[pos - 1].date
            if left + COURSE_SPAN + span > t:
                return False
        if pos < len(schedule_list):
            right = schedule_list[pos].date
            if right - span < t + tspan:
                return False
        return True


def _teacher_weeks(teacher_weeks):
    res = []
    m = re.search(week_single_grouped_re, teacher_weeks)
    while m:
        teacher_weeks = teacher_weeks[m.end() + 1:]
        teacher, week = m.groups()
        res.append((re.sub(r'\s', '', teacher), week))
        m = re.search(week_single_grouped_re, teacher_weeks)
    return res

def timespan(s: str):
    times = re.split('[,，]', s)
    res = []
    for ts in times:
        to = ts.rfind('-')
        if to < 0:
            res.append(int(ts))
        else:
            from_ = int(ts[:to])
            to = int(ts[to + 1:])
            for i in range(min(from_, to), max(from_, to) + 1):
                res.append(i)
    return sorted(res)

COURSE_SPAN = datetime.timedelta(minutes=45)

def time_lut(course_time):
    course_time = min(max(int(course_time), 1), 14)
    if course_time == 1:
        return datetime.timedelta(hours=8, minutes=0)
    if course_time == 2:
        return datetime.timedelta(hours=8, minutes=50)
    if course_time == 3:
        return datetime.timedelta(hours=9, minutes=50)
    if course_time == 4:
        return datetime.timedelta(hours=10, minutes=40)
    if course_time == 5:
        return datetime.timedelta(hours=11, minutes=30)
    if course_time == 6:
        return datetime.timedelta(hours=14, minutes=0)
    if course_time == 7:
        return datetime.timedelta(hours=14, minutes=50)
    if course_time == 8:
        return datetime.timedelta(hours=15, minutes=50)
    if course_time == 9:
        return datetime.timedelta(hours=16, minutes=40)
    if course_time == 10:
        return datetime.timedelta(hours=17, minutes=30)
    if course_time == 11:
        return datetime.timedelta(hours=19, minutes=0)
    if course_time == 12:
        return datetime.timedelta(hours=19, minutes=50)
    if course_time == 13:
        return datetime.timedelta(hours=20, minutes=50)
    if course_time == 14:
        return datetime.timedelta(hours=21, minutes=40)
    return NotImplemented

def mail(args, sender, password, receiver=None, server=None, title='Reminder', file='src/reminder.html'):
    with smtp.login_mail(sender, password, server=server) as s:
        return smtp.mail(s, smtp.mime_from_file(title, file, replace={'product_name': PRODUCT_NAME, **args}), receiver=receiver)

def remind(course_detail, sender, password, receiver=None, server=None, title='Reminder'):
    return mail({'course_detail': course_detail}, sender, password, receiver=receiver, server=server, title=title, file='src/reminder.html')

def bykc_notice(course: bykc.course, sender, password, receiver=None, server=None, title='BYKC Notice: Enrolled in %s'):
    return mail({
        'course_id': course.id,
        'course_name': course.name,
        'organizer': course.provider,
        'lecturer': course.teacher,
        'campus': course.campus,
        'classroom': course.classroom,
        'college': course.college,
        'start_time': date2str(course.start),
        'end_time': date2str(course.end),
        'enroll_start': date2str(course.select_start),
        'enroll_end': date2str(course.select_end),
        'description': course.desc if course.desc is not None else '',
        'max': course.max,
    }, sender, password, receiver=receiver, server=server, title=title % ('%s %s' % (course.id, course.name)), file='src/bykc_notice.html')


__all__ = [
    'BUAAException',
    'CASTGC',
    'login',
    'bykc',
    'jwxt',
    'mail',
    'remind',
    'bykc_notice',
]
