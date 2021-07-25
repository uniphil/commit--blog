from flask_mail import Mail, Message

mail = Mail()

transactional = ('commit --blog', 'mail@commit--blog.com')

templates = {}


templates['confirm_email'] = ('Please confirm your email address', transactional, """\
Hello {username}!

To finish adding this email address to your commit--blog account, please click here to confirm:

{confirm_url}


Thanks!

PS. If you didn't just sign up as {username} on commit--blog.com, ignore this message and we'll never email you again.
""")


templates['login_email'] = ('Your login code', transactional, """\
Hello {username},

Here is the code to finish logging in:

{token}

This code will expire in 10 minutes. Thanks!
""")
