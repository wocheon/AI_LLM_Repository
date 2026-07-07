# modules/history.py

class ConversationHistory:
    def __init__(self, max_turns=10):
        self.history = []
        self.max_turns = max_turns

    def add_user(self, content):
        self.history.append({"role": "user", "content": content})
        self._trim()

    def add_ai(self, content):
        self.history.append({"role": "assistant", "content": content})
        self._trim()

    def get_messages(self):
        return self.history

    def _trim(self):
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-(self.max_turns * 2):]

    def clear(self):
        self.history = []
