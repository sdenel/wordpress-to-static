#!/usr/bin/env python3
# coding: utf-8

# pip3 install requests

# TODO: get some CDN remote files and store them locally:
# For example https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/fonts/fontawesome-webfont.woff2?v=4.7.0 is slow to fetch

import shutil
import os
import requests
import pprint
import codecs
import hashlib
from urllib.parse import unquote, quote

# TODO: should be env variables
GET_DIR = 'www'
HOST = "rose.hopto.org"
CURRENT_BASE_URL = "https://rose.hopto.org/"
NEW_BASE_URL = 'http://localhost:8080/'
# Currently I am getting access to wordpress with:
# kubectl --namespace=production port-forward svc/wordpress 10000:80
LOCAL_ADDRESS = "http://localhost:10000"


def sha256sum(filename):
    h = hashlib.sha256()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(lambda: f.read(128 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def build_new_name(name):
    """
    >>> build_new_name('wp-content/uploads/2018/01/cropped-Logo-2.png')
    'wp-content/uploads/2018/01/cropped-Logo-2.png'
    >>> build_new_name('wp-includes/js/wp-embed.min.js?ver=4.9.7')
    'wp-includes/js/wp-embed.min.ver_4.9.7.js'
    >>> build_new_name('/feed/')
    '/feed.xml'
    """
    p_question_mark = name.find('?')
    if p_question_mark != -1:
        query_params = name[p_question_mark + 1:].replace("&", '_').replace('=', '_')
        name_elems = name[:p_question_mark].split('.')
        name = '.'.join(name_elems[:-1]) + '.' + query_params + '.' + name_elems[-1]
    if name.endswith("/feed/"):
        name = name[:-1] + '.xml'
    return name


def get_links(domain, str):
    """
    >>> get_links("https://something.org/", "script' src=\'https://something.org/wp-includes/js/wp-embed.min.js?ver=4.9.7'></sc")
    ['/wp-includes/js/wp-embed.min.js?ver=4.9.7']
    >>> get_links("https://something.org/", 'src="https://something.org/wp-includes/js/wp-embed.min.js?ver=4.9.7"></sc')
    ['/wp-includes/js/wp-embed.min.js?ver=4.9.7']
    >>> get_links("https://something.org/", '"logo" srcset="https://something.org/wp-content/uploads/2018/01/cropped-Logo-2.png 1094w, ')
    ['/wp-content/uploads/2018/01/cropped-Logo-2.png']
    >>> get_links("https://something.org/", 'set="https://something.org/feed/?someparam ') # Feeds do not take query params
    ['/feed/']
    >>> get_links("https://something.org/", 'set="https://something.org/wp-content/uploads/2018/02/tarte_brocolis_truite_chèvre.jpg" al')
    ['/wp-content/uploads/2018/02/tarte_brocolis_truite_ch%C3%A8vre.jpg']
    """
    str_split = str.split(domain)[1:]
    links = []
    for x in str_split:
        # print("         " + x)
        x = unquote(x)
        chrs = ['"', "'", ' ', '<', '#']
        p = [p for p in [x.find(chr) for chr in chrs] if p != -1]
        assert len(p) != 0, x
        url = x[:min(p)]
        if url.find('feed/?') != -1:
            url = url.split('?')[0]
        url = url.strip('\\')
        # print("Adding " + url)
        url = quote(url).replace("%3F", "?").replace("%3D", "=")
        links.append('/' + url)
    return links


def build_save_name(name):
    """
    >>> build_save_name('/something.html')
    '/something.html'
    >>> build_save_name('/hello/')
    '/hello/index.html'
    """
    if name.endswith('/'):
        return name + 'index.html'
    else:
        return name


def push_links(known_links, new_links):
    for l in new_links:
        if not l in known_links:
            print("    + " + l)
            known_links[l] = {
                'downloaded': False
            }
    return known_links


def drop_link(content, link):
    p = content.find(link)
    if p != -1:
        return content[:content[:p].rfind('<')] + content[content.find('>', p) + 1:]
    else:
        return content


def drop_admin_link(content):
    '''
    >>> drop_admin_link('><script type="text/javascript">var sbiajaxurl = "https://something.org/wp-admin/admin-ajax.php";</script><sc')
    '><sc'
    '''
    return drop_link(content, '/wp-admin/admin-ajax.php')


def drop_xmlrpc(domain, content):
    """
    >>> drop_xmlrpc('https://something.org/', ' /><link rel="pingback" href="https://something.org/xmlrpc.php" /><ti')
    ' /><ti'
    """
    content = drop_link(content, "href='" + domain + 'xmlrpc.php' + "'")
    content = drop_link(content, 'href="' + domain + 'xmlrpc.php' + '"')
    content = drop_link(content, "href='" + domain + 'xmlrpc.php?rsd' + "'")
    content = drop_link(content, 'href="' + domain + 'xmlrpc.php?rsd' + '"')
    return content


def drop_wp_json(domain, content):
    """
    >>> drop_wp_json('https://something.org/', "ript><link rel='https://api.w.org/' href='https://something.org/wp-json/' /><l")
    'ript><l'
    """
    content = drop_link(content, domain + 'wp-json/')
    content = drop_link(content, 'wp-json/oembed/')
    content = drop_link(content, 'text/xml+oembed')
    return content


def drop_shortlink(domain, content):
    """
    >>> drop_shortlink("https://something.org/", "/><link rel='shortlink' href='?p=29' /><lin")
    '/><lin'
    """
    content = drop_link(content, "href='" + domain + "?p=")
    content = drop_link(content, 'href="' + domain + '?p=')
    content = drop_link(content, "href='?p=")
    content = drop_link(content, "href=\\'?p=")
    content = drop_link(content, 'href="?p=')
    content = drop_link(content, "rel=\\'shortlink\\'")
    return content


if __name__ == '__main__':
    print("> Cleaning")
    if os.path.exists(GET_DIR) and os.path.isdir(GET_DIR):
        print("Removing " + GET_DIR)
        shutil.rmtree(GET_DIR)
    os.makedirs(GET_DIR)

    print("> Aspiration de $OLD_DOMAIN...")

    # subprocess.call(
    #     "wget --header='cookie: _oauth2_proxy=c2ltb25kZW5lbDFAZ21haWwuY29t|1532531463|t-c7xkljFr5YEnOPOAWCLpPoPfI=;' --recursive --no-parent https://rose.hopto.org/ 2>log",
    #     shell=True)

    links = []
    known_links_d = {
        '/': {'downloaded': False}
    }
    # wordpress.production.svc.cluster.local
    while True:
        links_to_get = [l for l in known_links_d if known_links_d[l]['downloaded'] == False]
        if len(links_to_get) == 0:
            break
        else:
            link_to_get = links_to_get[0]
            url = LOCAL_ADDRESS + link_to_get
            print("GET " + url)
            response = requests.get(url, headers = {'Host': HOST, 'X-Forwarded-Host': HOST})
            assert response.status_code == 200, "GET " + url + ": status_code = " + str(response.status_code)
            new_name = build_new_name(link_to_get)
            save_name = GET_DIR + build_save_name(new_name)
            known_links_d[link_to_get] = {
                'downloaded': True,
                'newName': new_name,
                'saveName': save_name
            }

            dir = '/'.join(save_name.split('/')[:-1])
            print("makedir:" + dir)
            if not os.path.exists(dir):
                os.makedirs(dir)

            # print(a.content)
            if response.encoding == "UTF-8":
                content_cleaned = drop_shortlink(
                    CURRENT_BASE_URL,
                    drop_admin_link(
                        drop_wp_json(
                            CURRENT_BASE_URL,
                            drop_xmlrpc(
                                CURRENT_BASE_URL,
                                str(response.content, "utf-8")
                            )
                        )
                    )
                ).replace("\\r\\n", "\n").replace('\\t', "\t")
                print("        -> Saving as:" + save_name)
                with codecs.open(save_name, "w", encoding='utf8') as f:
                    f.write(content_cleaned)
                links_l = get_links(CURRENT_BASE_URL, content_cleaned)
                push_links(known_links_d, links_l)
            else:
                print("        -> Saving as:" + save_name)
                with open(save_name, "wb") as f:
                    f.write(response.content)

    pprint.pprint(known_links_d)

    for f in known_links_d:
        save_name = known_links_d[f]['saveName']
        immutable_extensions = ['.js', '.css', '.png', '.jpg']
        if len([1 for x in immutable_extensions if save_name.endswith(x)]) == 1:
            print("Should add sha: " + save_name)
            sha = sha256sum(save_name)
            new_save_name = save_name[:save_name.rfind('.')] + "." + sha + save_name[save_name.rfind('.'):]
            new_name = known_links_d[f]['newName']
            new_new_name = new_name[:new_name.rfind('.')] + "." + sha + new_name[new_name.rfind('.'):]
            known_links_d[f]['newName'] = new_new_name
            os.rename(save_name, new_save_name)
            known_links_d[f]['saveName'] = new_save_name
            print(new_save_name)

    for root, dirs, files in os.walk(GET_DIR):
        path = root.split(os.sep)
        for file in files:
            if file.endswith(".html"):
                print("Opening:", root + '/' + file)
                with codecs.open(root + '/' + file, 'r', encoding='utf8') as myfile:
                    html = myfile.read()
                html = html.replace(CURRENT_BASE_URL, NEW_BASE_URL)
                for f in known_links_d:
                    html = html.replace(f, known_links_d[f]['newName'])
                with codecs.open(root + '/' + file, "w", encoding='utf8') as f:
                    f.write(html)
