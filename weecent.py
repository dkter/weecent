# -*- coding: utf-8 -*-

import weechat
import requests
import json
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

for url, data in servers.items():
    # ping the server, to see if it's online
    ping = requests.get(url)
    if ping.status_code != requests.codes.ok:
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
            buffer = weechat.buffer_new(server_name, "server_input_cb",
                "", "server_close_cb", "")
            weechat.buffer_set(buffer, "title", "Weecent testing!")
            weechat.buffer_set(buffer, "localvar_set_no_log", "1")
            weechat.buffer_set(buffer, "localvar_set_type", "server")
            weechat.buffer_set(buffer, "localvar_set_url", url)
            weechat.buffer_set(buffer, "localvar_set_server", server_name)

            # create channel buffers
            xd[url]["channels"] = {}
            for channel in channels:
                buffer = weechat.buffer_new(channel["name"], "send_message",
                    "", "channel_close_cb", "")
                weechat.buffer_set(buffer, "title", "Weecent testing!")
                weechat.buffer_set(buffer, "localvar_set_no_log", "1")
                weechat.buffer_set(buffer, "localvar_set_type", "channel")
                weechat.buffer_set(buffer, "localvar_set_channel",
                    json.dumps(channel))
                weechat.buffer_set(buffer, "localvar_set_url", url)
                weechat.buffer_set(buffer, "localvar_set_server", server_name)
                xd[url]["channels"][channel["id"]] = channel["name"]
        else:
            weechat.prnt("", "ono a bad happened")

        # create websocket
        if not "socket" in xd[url]:
            use_secure = requests.get(urljoin(url, "api/should-use-secure")).json()
            if use_secure["useSecure"]:
                xd[url]['socket'] = websocket.create_connection("wss://" + server_name)
            else:
                xd[url]['socket'] = websocket.create_connection("ws://" + server_name)
            weechat.hook_fd(xd[url]['socket'].sock._sock.fileno(), 1, 0, 0,
                "timer_cb", "")
    else:
        weechat.prnt("", "ono a bad happened")

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
            buffer_ = weechat.buffer_search("python",
                xd[server]["channels"][j["data"]["message"]["channelID"]])
            # display the message!
            weechat.prnt(buffer_, (j["data"]["message"]["authorUsername"] +
                            "\t" + j["data"]["message"]["text"]).encode("utf-8"))
    return weechat.WEECHAT_RC_OK

#weechat.hook_timer(60 * 1000, 60, 0, "timer_cb", "")
