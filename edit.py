# -*- coding: utf-8 -*-
import argparse
import hashlib
import json
import os
import re
import time

os.environ['PYWIKIBOT_DIR'] = os.path.dirname(os.path.realpath(__file__))
import pywikibot
from pywikibot.data.api import Request
from config import config_page_name  # pylint: disable=E0611,W0614

parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true')
parser.set_defaults(debug=False)
args = parser.parse_args()

os.environ['TZ'] = 'UTC'

site = pywikibot.Site()
site.login()

config_page = pywikibot.Page(site, config_page_name)
cfg = config_page.text
cfg = json.loads(cfg)

if not cfg['enable']:
    print('disabled\n')
    exit()

rrdpage = pywikibot.Page(site, cfg['rrd_page'])
text = rrdpage.text

rndstr = hashlib.md5(str(time.time()).encode()).hexdigest()

text = re.sub(r'({{Revdel)', rndstr + r'\1', text)
text = text.split(rndstr)

newtext = text[0]
remaincnt = 0

for secid in range(1, len(text)):
    sectext = text[secid].strip()

    m = re.search(r'\|\s*article\s*=\s*(.+?)\s*\|', sectext)
    if m:
        title = m.group(1)
        if args.debug:
            print(title)
        if re.search(r'\|\s*status\s*=\s*((新申請)?<!--(不要修改本参数|不要修改本參數)-->)?\s*\|', sectext):
            flag = 0
            if re.search(r'\|\s*set\s*=.*([編编][輯辑]|[刪删]除)?[內内]容', sectext):
                flag |= 1
                if args.debug:
                    print('\tcontent')
            if re.search(r'\|\s*set\s*=.*([編编][輯辑])?摘要', sectext):
                flag |= 2
                if args.debug:
                    print('\tsummary')
            if flag != 0:
                ids = re.findall(r'\|id\d+\s*=\s*(\d+)', sectext)
                if ids:
                    data = Request(site=site, parameters={
                        'action': 'query',
                        'list': 'logevents',
                        'leaction': 'delete/revision',
                        'lelimit': '10',
                        'letitle': title
                    }).submit()
                    deleted = 0
                    admins = {}
                    for logevent in data['query']['logevents']:
                        logid = str(logevent['logid'])
                        admin = logevent['user']
                        if args.debug:
                            print('\t', logevent)
                        if (logevent['params']['type'] == 'revision'
                                and logevent['params']['new']['bitmask'] & flag == flag):
                            for rvid in logevent['params']['ids']:
                                rvid = str(rvid)
                                if rvid in ids:
                                    deleted += 1
                                    if admin not in admins:
                                        admins[admin] = {}
                                    if logid not in admins[admin]:
                                        admins[admin][logid] = 0
                                    admins[admin][logid] += 1
                        if deleted == len(ids):
                            break

                    for admin in admins:
                        logids = []
                        delcnt = 0
                        for logid in admins[admin]:
                            if logid not in sectext:
                                logids.append(logid)
                                delcnt += admins[admin][logid]
                        if logids:
                            if deleted == len(ids) and len(admins) == 1:
                                sectext += '\n' + cfg['comment_delete_all'].format(
                                    admin, '<!-- ' + ','.join(logids) + ' -->')
                            else:
                                sectext += '\n' + cfg['comment_delete_partial'].format(
                                    admin, delcnt, '<!-- ' + ','.join(logids) + ' -->')

                    if deleted == len(ids):
                        sectext = re.sub(
                            r'(\|\s*status\s*=).*', r'\1 +', sectext)
                    else:
                        remaincnt += 1

                    if args.debug:
                        print('\tdeleted {}/{} in {}'.format(deleted, len(ids), admins))

                else:
                    if args.debug:
                        print('\tcannot get ids')
                    remaincnt += 1
            else:
                if args.debug:
                    print('\tcannot detect type')
                remaincnt += 1
        else:
            if args.debug:
                print('\tdone')
    else:
        if args.debug:
            print('cannot get article')
    newtext += sectext + '\n\n'


if re.sub(r'\s', '', rrdpage.text) == re.sub(r'\s', '', newtext):
    if args.debug:
        print('nothing changed')
    exit()

pywikibot.showDiff(rrdpage.text, newtext)
rrdpage.text = newtext
summary = cfg['summary'].format(remaincnt)
rrdpage.save(summary=summary, minor=True)
