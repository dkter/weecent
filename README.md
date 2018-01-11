# weecent
WeeChat script for [Decent](https://github.com/towerofnix/decent).

This project is in alpha stage and is not stable. If something breaks, let me know in the issue tracker.

## What can it do?
- Connect to HTTP and HTTPS Decent servers (can't connect to multiple servers at once though)
- Send messages
- Receive messages
- Get scrollback
- Show a nicklist with online/offline indicators
- Handle mentions

## How do I use it?

```
git clone https://github.com/TheInitializer/weecent.git
cd weecent
cp weecent.py ~/.weechat/python/autoload/
```

Then, in WeeChat:

```
/set plugins.var.python.weecent.servers {"https://YOUR_DECENT_SERVER_HERE.com": {"username": "YOUR_USERNAME_HERE", "password": "YOUR_PASSWORD_HERE"}}
