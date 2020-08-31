import functools
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import cv2
import numpy as np
from functools import partial
import sys
import os
import logging
import json
import time
import requests
import shutil
import pathlib

import hashlib
encrypt = hashlib.md5


# from watchdog.events import LoggingEventHandler

APPID = ''
SERECT = ''

TOKEN = ''
UPDATE_TOKEN_TIME = 0
ROOT_DIR = ''

def log(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        elaps = time.time() - start
        name = func.__name__
        print('[%0.8fs] %s' % (elaps, name))
        return res
    return wrapper

# get ACCESS_TOKEN
def get_token(appid: str, secret: str) -> (str, str):
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    res = requests.get(url).text

    res = json.loads(res)
    if hasattr(res, 'errcode'):
        logging.warning(res)
        sys.exit(0)
    return res['access_token'], res['expires_in']

# resize img 2 times smaller by every recursion
def img_resize(bin_img: bytes, ratio: int = 2) -> bytes:
    if len(bin_img) < 5 * (1 << 20):
        return bin_img

    try:        
        arr = np.frombuffer(bin_img, dtype=np.uint8, count=-1)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

        h, w = img.shape[:2]
        h = h // ratio
        w = w // ratio
        img = cv2.resize(img, (w, h))

        _, buffer = cv2.imencode(".jpg", img)
        ratio_bin_img = bytes(list(np.squeeze(buffer)))        
        return img_resize(ratio_bin_img, ratio)
    except Exception as e:
        print(e)        

# img compression 
def img_downsize(bin_img: bytes, ratio: int = 50) -> bytes:   
    bin_img = img_resize(bin_img)

    if len(bin_img) < (1 << 20) or ratio < 10:
        return bin_img    
    # to ndarray
    arr = np.frombuffer(bin_img, dtype=np.uint8, count=-1)
    
    try:
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        state, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, ratio])
        ratio_bin_img = bytes(list(np.squeeze(buffer)))
        return img_downsize(ratio_bin_img, ratio // 2)
    except Exception as e:
        print(e)


def msg_slice(bin_msg: bytes):
    # TODO
    pass

# adjust size
def content_sizeCheck(content: bytes) -> bytes:
    file_info = str(content[0]) + str(content[1])

    # img
    if file_info in ['255216', '7173', '6677', '13780']:
        return img_downsize(content, 70)
    else:
    # msg
        pass

# sensetive info recognition of upload content
def content_check(upload_file: str, token: str) -> (str, dict):
    try:
        with open(upload_file, 'rb') as up_f:
            content = up_f.read()
    except:
        content = None

    if not content:
        return None, {'errcode': None, 'errmsg': None}
    digest = encrypt(content).hexdigest()
    # 255216 jpg; 7173 gif; 6677 BMP, 13780 PNG; 7790 exe, 8297 rar
    file_info = str(content[0]) + str(content[1])
    fmt = 'https://api.weixin.qq.com/wxa/{}_sec_check?access_token=' + token

    # generate satisfied upload file size if oversized
    content = content_sizeCheck(content)

    # img content encode detect
    if file_info in ['255216', '7173', '6677', '13780']:
        url = fmt.format('img')

        # content: bytes of raw img
        files = {"media": content}
        headers = {'Content-Type': 'multipart/form-data'}
        res = requests.post(url, files=files, headers=headers)
    else:
        # msg content
        url = fmt.format('msg')

        # content: bytes of str dict
        headers = {'Content-Type': 'application/json'}
        res = requests.post(url, data=content, headers=headers)

    print(res.json())
    return digest, res.json()


# duplicate file name detect
# dupilicate name with suffix "fillname(incremental key)"
def dup_search(name: str, dup: str):
    if len(dup) - len(name) < 3:
        return 0
    if dup[:len(name)] == name and dup[len(name)] == '(' and dup[-1] == ')':
        return int(dup[len(name)+1:-1])
    else:
        return 0

# handle name duplication of upload file
def file_op(src: 'pathlib.Path', dst: "pathlib.Path", op='move'):
    if dst.exists():
        replica = [f.stem for f in dst.parent.iterdir()]
        f = partial(dup_search, src.stem)
        maxn = max(list(map(f, replica)))
        if not maxn:
            maxn = 1
        name = src.stem + f'({maxn + 1})' + src.suffix
        dst = dst.parent / name
    if op == 'move':    shutil.move(str(src), str(dst))
    elif op == 'copy':  shutil.copy(str(src), str(dst))

# handle response errcode
def handle_recognized_img(upload_file: str, code: int):
    # filter img to dst directory
    global TOKEN, APPID, SERECT, UPDATE_TOKEN_TIME, ROOT_DIR

    if code == 0:
        pass
        # file_op(upload_file, ROOT_DIR /
        #           'checked' / upload_file.name, 'move')
    elif code == 87014:
        file_op(upload_file, ROOT_DIR /
                'risky' / upload_file.name, 'move')
    elif code == 42001 or code == 41001:
        # code expire or code missing
        try:
            TOKEN, duration = get_token(APPID, SERECT)
            UPDATE_TOKEN_TIME = time.time() + duration
            _, res = content_check(upload_file, TOKEN)
            handle_recognized_img(upload_file, res['errcode'])
        except:
            file_op(upload_file, ROOT_DIR /
                    'unchecked' / upload_file.name, 'copy')
    else:
        file_op(upload_file, ROOT_DIR /
                'error' / upload_file.name, 'copy')


class LoggingEventHandler(FileSystemEventHandler):
    """Logs all the events captured."""

    def on_created(self, event):
        super(LoggingEventHandler, self).on_created(event)
        what = 'directory' if event.is_directory else 'file'

        logging.info("Created %s: %s", what, event.src_path)

    def on_deleted(self, event):
        super(LoggingEventHandler, self).on_deleted(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Deleted %s: %s", what, event.src_path)
        
    @log
    def on_modified(self, event):
        super(LoggingEventHandler, self).on_modified(event)

        global TOKEN, UPDATE_TOKEN_TIME, APPID, SERECT, ROOT_DIR
        if time.time() > UPDATE_TOKEN_TIME:
            TOKEN, duration = get_token(APPID, SERECT)
            UPDATE_TOKEN_TIME = time.time() + duration
        what = 'directory' if event.is_directory else 'file'

        f = open(ROOT_DIR / "uploads.log", 'a+')
        upload_file = pathlib.Path(event.src_path)

        # img suffix detect
        if what == 'file' and upload_file.suffix in ['.jpg', '.png', '.gif', '.ico']:
            logging.info(f"content-check for {upload_file}")
            digest, res = content_check(upload_file, TOKEN)

            # log
            logging.info(f"{upload_file} result with errcode {res['errcode']}")
            code = res['errcode']
            filename = upload_file.name
            upload_date = time.strftime("%Y/%D-%T")
            line = f"{digest},{filename},{code},{res['errmsg']},{upload_date}\n"
            f.write(line)

            handle_recognized_img(upload_file, code)

            if code !=  0:
                url = f"https://fds.leduo.cn/callback_secImage.php?file={upload_file}&errcode={code}&errmsg={res['errmsg']}"
                requests.post(url)
                # shutil.copy('C:/Users/Administrator/wcw/file_monitor/err.png', upload_file)
                shutil.copy('/www/wwwroot/fds.leduo.cn/Uploads/images/err.png', filename)

        f.close()
        logging.info("Modified %s: %s", what, event.src_path)

def file_monitor(uploads_dir: str = ''):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = uploads_dir if uploads_dir else '.'

    # check logfile
    path = pathlib.Path(os.path.abspath(path))
    logging.info(f"Monitoring directory {str(path.absolute())}")

    # the place (../) where wrong img to go
    for folder in ['risky', 'unchecked', 'error']:
        os.makedirs(path.parent / folder , exist_ok=True)

    global ROOT_DIR
    ROOT_DIR = path.parent

    if not (ROOT_DIR / "uploads.log").exists():
        f = open(ROOT_DIR / "uploads.log", 'w')
        line = "img_id,img_name,code,response_msg,upload_date\n"
        f.write(line)
        f.close()    

    event_handler = LoggingEventHandler()

    observer = Observer()
    observer.schedule(event_handler, str(path), recursive=True)
    observer.start()
    logging.info('Observer start, waiting for image uploads')

    iStart = time.time()
    try:
        while True:
            if time.time() - iStart >= 300:
                with open(path /'lastCheckPoint.time', 'w') as f:
                    f.write(time.strftime("%Y/%D-%T"))
                iStart = time.time()            
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    try:
        TOKEN, expire = get_token(APPID, SERECT)
        UPDATE_TOKEN_TIME = time.time() + expire
        path = sys.argv[1] if len(sys.argv) > 1 else '.'
        file_monitor(path)
    except Exception as e:
        print(e)
