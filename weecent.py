# -*- coding: utf-8 -*-

import weechat
import requests
import json
import re
import ssl
import websocket
from urlparse import urlparse, urljoin

weechat.register(
    "weecent",
    "xn--cr8h",
    "0",
    "BSD 3-Clause",
    "WeeChat plugin for Decent",
    "", "")

weechat.prnt("", "weecent\thi i'm weecent")

# set default servers
servers = {
    "https://server-url-here.com": {
        "username": "YOUR_USERNAME_HERE",
        "password": "YOUR_PASSWORD_HERE"
    }
}

script_options = {
    "servers": json.dumps(servers),
}
for option, default_value in script_options.items():
    if not weechat.config_is_set_plugin(option):
        weechat.config_set_plugin(option, default_value)

servers = json.loads(weechat.config_string(
    weechat.config_get("plugins.var.python.weecent.servers")))
xd = dict(servers)     # i couldn't figure out what to call this,
                       # and eq told me to call it `xd`

sslopt_ca_certs = {}
if hasattr(ssl, "get_default_verify_paths") and callable(ssl.get_default_verify_paths):
    ssl_defaults = ssl.get_default_verify_paths()
    if ssl_defaults.cafile is not None:
        sslopt_ca_certs = {'ca_certs': ssl_defaults.cafile}


# functions ##################################################################


def display_msg(buffer_, message, server, tag = "notify_none"):
    ping_re = r"\b" + server["username"] + r"\b"

    weechat.prnt_date_tags(
        buffer_,
        message["date"] / 1000,
        "notify_highlight" if re.findall(ping_re, message["text"]) else tag,
        (message["authorUsername"] + "\t" + message["text"]).encode("utf-8"))


# callbacks ##################################################################


# callback for data received in input for channel buffers
def send_message(data, buffer, input_data):
    channel_json = weechat.buffer_get_string(buffer, "localvar_channel")
    url = weechat.buffer_get_string(buffer, "localvar_url")
    channel = json.loads(channel_json)
    message_data = {
        "text": input_data,
        "channelID": channel['id'],
        "sessionID": session_id
    }
    r = requests.post(urljoin(url, "api/send-message"), json=message_data)
    return weechat.WEECHAT_RC_OK


# callback called when channel buffer is closed
def channel_close_cb(data, buffer):
    return weechat.WEECHAT_RC_OK


# callback for data received in input for server buffers
def server_input_cb(data, buffer, input_data):
    return weechat.WEECHAT_RC_OK


# callback called when server buffer is closed
def server_close_cb(data, buffer):
    return weechat.WEECHAT_RC_OK


# timer for receiving messages
def timer_cb(data, remaining_calls):
    for server in xd:
        message_data = xd[server]['socket'].recv()
        j = json.loads(message_data)
        if j['evt'] == "received chat message":
            # get buffer that corresponds to the channel ID
            buffer_ = weechat.buffer_search(
                "python",
                xd[server]["channels"][j["data"]["message"]["channelID"]])
            # display the message!
            display_msg(buffer_, j["data"]["message"], xd[server],
                        "notify_message")
    return weechat.WEECHAT_RC_OK


# populate buffers, open sockets, set everything up ##########################


for url, data in servers.items():
    # ping the server, to see if it's online
    ping = requests.get(urljoin(url, "api"))
    if ping.status_code == requests.codes.teapot and "decent" in ping.json():
        weechat.prnt(
            "", "weecent\tSuccessfully connected to Decent server %s." % url)
    elif ping.status_code in (requests.codes.ok, requests.codes.not_found):
        weechat.prnt(
            "", "weecent\t%s is not a valid Decent server, skipping." % url)
        del xd[url]
        continue
    else:
        weechat.prnt("", "weecent\tCould not connect to %s, skipping." % url)
        del xd[url]
        continue

    # login
    login_r = requests.post(urljoin(url, "api/login"), json=data)
    login_data = login_r.json()

    server_name = url.split("//")[1]
    if login_data["success"]:
        session_id = login_data["sessionID"]
        channels_r = requests.get(urljoin(url, "api/channel-list"),
                                  {'sessionID': session_id})
        if channels_r.json()['success']:
            channels = channels_r.json()['channels']

            # create server buffer
            buffer_ = weechat.buffer_new(server_name, "server_input_cb",
                                         "", "server_close_cb", "")
            weechat.buffer_set(buffer_, "title", "Weecent testing!")
            weechat.buffer_set(buffer_, "localvar_set_no_log", "1")
            weechat.buffer_set(buffer_, "localvar_set_type", "server")
            weechat.buffer_set(buffer_, "localvar_set_url", url)
            weechat.buffer_set(buffer_, "localvar_set_server", server_name)

            # create channel buffers
            xd[url]["channels"] = {}
            for channel in channels:
                # set up buffer
                buffer_ = weechat.buffer_new(channel["name"], "send_message",
                                             "", "channel_close_cb", "")
                weechat.buffer_set(buffer_, "title", "Weecent testing!")
                weechat.buffer_set(buffer_, "localvar_set_no_log", "1")
                weechat.buffer_set(buffer_, "localvar_set_type", "channel")
                weechat.buffer_set(buffer_, "localvar_set_channel",
                                   json.dumps(channel))
                weechat.buffer_set(buffer_, "localvar_set_url", url)
                weechat.buffer_set(buffer_, "localvar_set_server", server_name)
                xd[url]["channels"][channel["id"]] = channel["name"]

                # get scrollback
                scrollback_r = requests.get(
                    urljoin(url, "api/channel/%s/latest-messages" % channel["id"]))
                messages = scrollback_r.json()["messages"]
                for m in messages:
                    display_msg(buffer_, m, xd[url])
        else:
            weechat.prnt("", "ono a bad happened")

        # create websocket
        if not "socket" in xd[url]:
            # wss or ws?
            use_secure = requests.get(
                urljoin(url, "api/should-use-secure")).json()
            protocol = "wss://" if use_secure["useSecure"] else "ws://"

            xd[url]['socket'] = websocket.create_connection(
                protocol + server_name, sslopt = sslopt_ca_certs)

            weechat.hook_fd(xd[url]['socket'].sock._sock.fileno(), 1, 0, 0,
                            "timer_cb", "")
            xd[url]['socket'].sock.setblocking(0)
    else:
        weechat.prnt("", "ono a bad happened")
