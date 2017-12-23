# weecent
WeeChat script for [Decent](https://github.com/towerofnix/decent)

## What can it do?
- Connect to HTTP and HTTPS Decent servers (can't connect to multiple servers at once though)
- Send messages
- Receive messages

## How do I use it?

```
git clone https://github.com/TheInitializer/weecent.git
cd weecent
cp weecent.py ~/.weecent/python/autoload/
```

Then, in WeeChat:

```
/ser plugins.var.python.weecent.servers {"https://YOUR_DECENT_SERVER_HERE.com": {"username": "YOUR_USERNAME_HERE", "password": "YOUR_PASSWORD_HERE"}}
