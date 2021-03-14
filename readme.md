# commit --blog

Commit messages hold rich histories. They [document lines of code](https://mislav.net/2014/02/hidden-documentation/), express frustrations and victories, and record research, debates, and social context. If [code is more often read than written](https://devblogs.microsoft.com/oldnewthing/20070406-00/?p=27343), maybe its commit message annotations aren't read enough?

**commit --blog** is an experiment. It takes the writing we already do as programmers, and lifts it from the obscure depths of the terminal. Why must developer blogs live in a separate place from the content they’re about? And why can’t commit messages be as deep and context-filled as blog posts? Whether your goal is to share your writing with the world, or just to have a quiet feed of past commits to reflect on at the end of a project, **commit --blog** gets you started with the commits you’re already writing.

## Creating a commit --blog

If you use Git, you’ve already begun! To create a public **commit --blog** of your own, you don’t need to dive deeper into this repo. Go to https://commit--blog.com, follow the instructions there to create an account, and start picking some of your favourite commits to publish.

### Example blogs

To see what a **commit --blog** can look like, check out some active blogs:

- https://uniphil.commit--blog.com
- https://rileyjshaw.commit--blog.com
- Add your own by [submitting a pull request](https://github.com/uniphil/commit--blog/edit/master/readme.md)!

## Contributing

We’re still working on this part of the README. For now, you can [check out the project’s active issues](https://github.com/uniphil/commit--blog/issues).

### Things you'll need

1. A working python3.8+ installation. Try running `python3 --version` in a terminal. If it prints back something like `Python 3.9.0`, you're all set!
2. A set of GitHub OAuth application keys. Head over to [this form](https://github.com/settings/developers) to create a new application. The following settings are recommended:
    - *Application name*: `commit --blog local dev`
    - *Homepage URL*: `http://127.0.0.1:5000`
    - *Authorization callback URL*: `http://127.0.0.1:5000/gh/authorized`

    Once your application is submitted, take note of the *Client ID* and *Client secrets*. You'll need these later in the setup.

### Getting set up

1. Clone and enter this repository
   ```bash
   [phil@asdf:~/code]$ git clone git@github.com:uniphil/commit--blog.git

       Cloning into 'commit--blog'...
       remote: Enumerating objects: 218, done.
       remote: Counting objects: 100% (218/218), done.
       remote: Compressing objects: 100% (149/149), done.
       remote: Total 552 (delta 108), reused 158 (delta 59), pack-reused 334
       Receiving objects: 100% (552/552), 1.11 MiB | 1.67 MiB/s, done.
       Resolving deltas: 100% (287/287), done.

   [phil@asdf:~/code]$ cd commit--blog/
   ```

2. Create a virtualenv and install the project dev dependencies
   ```bash
   [phil@asdf:~/code/commit--blog]$ python3 -m venv venv

   [phil@asdf:~/code/commit--blog]$ venv/bin/pip install -r requirements.dev.txt
        Collecting python-dotenv~=0.15.0

    [... plus a whole lot more output. this command can take a minute]

        Successfully installed [approximately 1 million packages]
   ```

3. Copy `.env.example` to `.env` and add your github oauth keys
   ```bash
   [phil@asdf:~/code/commit--blog]$ cp .env.example .env

   [phil@asdf:~/code/commit--blog]$ nano .env

     GNU nano 2.0.6         File: .env

        DEBUG=True
        FLASK_ENV=development
        SECRET_KEY=abc

        GITHUB_CLIENT_ID=<add your client id here>
        GITHUB_CLIENT_SECRET=<add your secret key here>

   [hint: press ctrl+o to save, ctrl+x to exit]
   ```

4. Initialize the database
   ```bash
   [phil@asdf:~/code/commit--blog]$ ./manage.py initdb
   ```

5. Run it!!!
   ```bash
   [phil@asdf:~/code/commit--blog]$ ./manage.py runserver
     * Serving Flask app "commitblog" (lazy loading)
     * Environment: development
     * Debug mode: on
     * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
     * Restarting with stat
     * Debugger is active!
     * Debugger PIN: XXX-XXX-XXX

   ```
   Leave that terminal running and head over to [`http://127.0.0.1:5000`](http://127.0.0.1:5000) in a browser. Hopefully you will see the home page! You're all set!


## License

…coming soon?
