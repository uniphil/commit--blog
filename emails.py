from flask_mail import Mail, Message

mail = Mail()

transactional = ('commit --blog', 'mail@commit--blog.com')

templates = {}

templates['hello'] = ('Welcome and hello!', transactional, """
Hello there!

This is a message. Here's a value: {value}

Thanks!
""")
