"""Helper module."""
import os
import re
from configparser import ConfigParser, NoOptionError, ParsingError

from git import Repo, exc


class DailyProgrammerHelper(object):
    """Singleton helper used to transform messages into a md file."""

    __instance = None
    __directory = 'ToBePublished/'
    __filename = 'index.md'
    # separate challenges with a line
    __challenges_separator = "\n\n\n---\n\n\n"

    CHALLENGE_REGEX = re.compile(
        r"===?\s+([\w\s]+)\-?[\w\s]*\s+=?==")
    __CODE_BLOCS_REGEX = re.compile(r"(```)((?:[^`]*\n*)*?)(```)")
    __TITLE_REGEX = re.compile((r"(?:\*\={3}\s)(.*)(?:\s-\sDaily\sProgrammer"
                                r"\s\={3}\*\n*?\*\[)(.*)(?:\]\*)"))
    __IMAGES_REGEX = re.compile(
        r"<(https://assets\.leetcode\.com/uploads/.*?)>")

    __REPO_URL = 'git@github.com:73VW/Daily-Programmer-Bot.git'

    __CONFIG_FILE_PATH = 'config.ini'

    @staticmethod
    async def getInstance():
        """Return or create and return instance."""
        if DailyProgrammerHelper.__instance is None:
            DailyProgrammerHelper()
        return DailyProgrammerHelper.__instance

    def __init__(self):
        """Virtually private constructor."""
        if DailyProgrammerHelper.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            DailyProgrammerHelper.__instance = self
            self.read_config()

    def read_config(self):
        """Read config from config.ini file.

        Exceptions are raised if the config file is not correct.

        File content :

        [GitRepoInfo]
        repo = git@github.com:73VW/Daily-Programmer-Bot.git

        """
        config_object = ConfigParser()
        try:
            config_object.read(self.__CONFIG_FILE_PATH)
            git_repo_info = config_object["GitRepoInfo"]
            repo = git_repo_info["repo"]

            if repo is None or repo == '':
                raise NoOptionError('repo', section='GitRepoInfo')

            self.__REPO_URL = git_repo_info["repo"]

        except (NoOptionError, ParsingError, KeyError) as e:
            message = '\n/!\\ \n\n'
            message += f'Invalid {self.__CONFIG_FILE_PATH} file \n'
            if isinstance(e, NoOptionError):
                message += f'Check option "{e.option}" in section "{e.section}"'
            elif isinstance(e, KeyError):
                message += f'Missing section {e}'
            message += '\nContent should look like:\n'
            message += '[GitRepoInfo]\n'
            message += 'repo = git@github.com:73VW/Daily-Programmer-Bot.git'
            message += '\n\n\nUSING DEFAULT REPO'
            print(message)

    async def parse_channel_history(self, channel_history):
        """Parse channel_history and find messages matching CHALLENGE_REGEX.

        Parameters:
        channel_history (slack_sdk.web.async_slack_response.AsyncSlackResponse)
        : AsyncResponse containing all messages from the channel

        Returns: None

        """
        print("Parsing and formating history...")
        complete_history = ""
        # recover only messages
        messages = channel_history.get('messages')
        # parse messages
        for message in reversed(messages):
            try:
                text = await self.format_messages(message)
                complete_history += text + self.__challenges_separator
            except MessageTypeException:
                pass
        print("Done...")
        if complete_history != "":
            await self.write_history_to_file(complete_history, 'w')

    async def parse_message(self, message):
        """Parse message.

        Parameter:
        message (dict): Message to format

        Returns: None

        """
        try:
            text = await self.format_messages(message)
            await self.write_history_to_file(text)
        except MessageTypeException:
            pass

    async def format_messages(self, message):
        """Format messages.

        Parameter:
        message (dict): Message to format

        Returns: None


        0. Check if message has text. If so, check if it has the right pattern.

        1. Format first 3 lines (Date and subject) and add '## ' at the \
beginning of first line.

        2. Check and format code blocs.

        3. Check and format images links.
        """
        """
        Ex.

        From:
        *=== Wednesday October 27th 2020 - Daily Programmer ===*

        *[Binary Tree Postorder Traversal]*

        To:
        # Binary Tree Postorder Traversal -- Wednesday October 27th 2020

        3. As code blocks in messages look that way when coming from Slack:
        ```Input: root = []
        Output: []```
        We need to format it in order to be correct markdown like so:
        ```
        Input: root = []
        Output: []
        ```
        """
        text = message.get('text')
        if text is None or not self.CHALLENGE_REGEX.search(text):
            raise MessageTypeException("The message doesn't match the pattern",
                                       message)

        # 1st modification
        text = "## " + re.sub(self.__TITLE_REGEX, r"\2 -- \1", text)
        # 2nd modification
        text = re.sub(self.__CODE_BLOCS_REGEX, r"\1\n\2\n\3", text)
        # 3rd modification
        text = re.sub(self.__IMAGES_REGEX, r"![Illustration](\1)\n", text)
        return text

    async def write_history_to_file(self, challenges, mode='a'):
        """Write challenge(s) to file.

        Parameters:
        challenges (string): challenge(s) to write to disk

        mode (char): a or w. Sets mode for file opening.

        Returns: None

        """
        print("Writing history to file...")
        if mode not in ('a', 'w'):
            raise FileOpeningModeException("Given mode isn't 'a' or 'w'!")

        # check if directory exists or create it
        if not os.path.isdir(self.__directory):
            os.mkdir(self.__directory)

        # write in file
        with open(os.path.join(self.__directory, self.__filename), mode) as f:
            f.writelines(challenges)
        print("Done...")
        await self.publish_challenges()

    async def publish_challenges(self):
        """Publish challenges to the gh_pages branches of the repo."""
        print("Publishing result...")
        remote_name = 'origin'
        new_branch = 'gh-pages'
        repo = None

        try:
            # Try to use local repo if it exists
            repo = Repo(self.__directory)
            repo.git.add('.')
            repo.git.commit('--amend', '--no-edit')
            repo.git.push('-f')
        except exc.InvalidGitRepositoryError:
            # Otherwise create it and configurate it
            repo = Repo.init(self.__directory)
            with repo.config_writer() as config:
                config.add_value('user', 'name', 'Daily Programmer Bot')
                config.add_value('user', 'email', 'daily@programmer.bot')
            origin = repo.create_remote(
                remote_name, self.__REPO_URL)
            repo.git.add('.')
            repo.git.commit(m="Deploying to gh-pages")
            current_branch = repo.create_head(new_branch)
            current_branch.checkout()
            origin.fetch()
            repo.git.push('-f', '--set-upstream', remote_name, current_branch)

        print("Done.")


class MessageTypeException(Exception):
    """Exception raised when a message doesn't match the challenge pattern."""

    def __init__(self, error, message):
        """Init exception."""
        self.error = error
        self.message = message


class FileOpeningModeException(Exception):
    """Exception raised when the file opening mode is not 'a' or 'w'."""

    def __init__(self, error):
        """Init exception."""
        self.error = error
