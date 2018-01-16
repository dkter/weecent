# -*- coding: utf-8 -*-

import weechat
import requests
import json
import re
import ssl
import websocket
from urlparse import urlparse, urljoin
from copy import deepcopy

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
xd = deepcopy(servers)     # i couldn't figure out what to call this,
                           # and eq told me to call it `xd`

sslopt_ca_certs = {}
if hasattr(ssl, "get_default_verify_paths") and callable(ssl.get_default_verify_paths):
    ssl_defaults = ssl.get_default_verify_paths()
    if ssl_defaults.cafile is not None:
        sslopt_ca_certs = {'ca_certs': ssl_defaults.cafile}


# functions ##################################################################


def connect(url, data):
    global xd
    # ping the server, to see if it's online
    ping = requests.get(urljoin(url, "api"))
    if ping.status_code == requests.codes.teapot and "decent" in ping.json():
        weechat.prnt(
            "", "weecent\tSuccessfully connected to Decent server %s." % url)
    elif ping.status_code in (requests.codes.ok, requests.codes.not_found):
        weechat.prnt(
            "", "weecent\t%s is not a valid Decent server, skipping." % url)
        del xd[url]
        return
    else:
        weechat.prnt("", "weecent\tCould not connect to %s, skipping." % url)
        del xd[url]
        return

    # login
    login_r = requests.post(urljoin(url, "api/login"), json=data)
    login_data = login_r.json()

    server_name = url.split("//")[1]
    if login_data["success"]:
        session_id = login_data["sessionID"]
        xd[url]["session_id"] = session_id

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
            xd[url]["buffer"] = buffer_

            # create channel buffers
            xd[url]["channels"] = {}
            for channel in channels:
                xd[url]["channels"][channel["id"]] = {"name": channel["name"]}

                # set up buffer
                buffer_ = weechat.buffer_new(channel["name"], "send_message",
                                             "", "channel_close_cb", "")
                weechat.buffer_set(buffer_, "title", "Weecent testing!")
                weechat.buffer_set(buffer_, "nicklist", "1")
                weechat.buffer_set(buffer_, "nicklist_display_groups", "0")
                weechat.buffer_set(buffer_, "localvar_set_no_log", "1")
                weechat.buffer_set(buffer_, "localvar_set_type", "channel")
                weechat.buffer_set(buffer_, "localvar_set_channel",
                                   json.dumps(channel))
                weechat.buffer_set(buffer_, "localvar_set_url", url)
                weechat.buffer_set(buffer_, "localvar_set_server", server_name)
                xd[url]["channels"][channel["id"]]["buffer"] = buffer_

                # get scrollback
                scrollback_r = requests.get(
                    urljoin(url, "api/channel/%s/latest-messages" % channel["id"]))
                messages = scrollback_r.json()["messages"]
                for m in messages:
                    display_msg(buffer_, m, xd[url])

                # get users
                users_r = requests.get(urljoin(url, "api/user-list"))
                users = users_r.json()["users"]

                group = weechat.nicklist_add_group(buffer_, "", "Users",
                    "weechat.color.nicklist_group", 1)

                for u in users:
                    weechat.nicklist_add_nick(buffer_, group, u["username"],
                        "default" if u["online"] else "lightgrey",
                        "", "lightgreen", 1)
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
                            "recv_cb", "")
            xd[url]['socket'].sock.setblocking(0)
    else:
        weechat.prnt("", "ono a bad happened")


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
        "sessionID": xd[url]["session_id"]
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


# callback for receiving messages
def recv_cb(data, remaining_calls):
    for server in xd:
        try:
            message_data = xd[server]["socket"].recv()
            j = json.loads(message_data)

            if j["evt"] == "message/new":
                # get buffer that corresponds to the channel ID
                buffer_ = weechat.buffer_search(
                    "python",
                    xd[server]["channels"][j["data"]["message"]["channelID"]]["name"])

                # display the message!
                display_msg(buffer_, j["data"]["message"], xd[server],
                            "notify_message")

            elif j["evt"] == "pingdata":
                pong_data = json.dumps({"evt": "pongdata", "data": {
                    "sessionID": xd[server]["session_id"]}})
                xd[server]["socket"].send(pong_data)
        except websocket.WebSocketConnectionClosedException:
            weechat.prnt("", "weecent\tLost connection to server %s. Reconnecting..."
                             % server)

            # close socket
            xd[server]["socket"].close()
            del xd[server]["socket"]

            # delete everything because I'm lazy
            weechat.buffer_close(xd[server]["buffer"])
            for channel in xd[server]["channels"].itervalues():
                weechat.buffer_close(channel["buffer"])

            connect(server, servers[server])
        except ssl.SSLWantReadError:
            # not sure what to do here.
            # it doesn't seem to affect execution much so I'll just ignore it
            # todo: figure out what this means
            weechat.prnt("", "weecent\ti got that darn ssl error again")

    return weechat.WEECHAT_RC_OK


# timer for updating the online/offline list
def nicklist_timer(data, remaining_calls):
    for server in xd:
        users_r = requests.get(urljoin(server, "api/user-list"))
        users = users_r.json()["users"]
        for channel in xd[server]["channels"].itervalues():
            weechat.nicklist_remove_all(channel["buffer"])
            group = weechat.nicklist_add_group(channel["buffer"], "", "Users",
                    "weechat.color.nicklist_group", 1)
            for u in users:
                weechat.nicklist_add_nick(
                    channel["buffer"],
                    group,
                    u["username"],
                    "default" if u["online"] else "lightgrey",
                    "", "lightgreen", 1)
    return weechat.WEECHAT_RC_OK

weechat.hook_timer(30 * 1000, 30, 0, "nicklist_timer", "")


# populate buffers, open sockets, set everything up ##########################


for url, data in servers.items():
    connect(url, data)
