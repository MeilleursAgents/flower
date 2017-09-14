from tornado.web import RequestHandler


class PingView(RequestHandler):
    def get(self):
        self.write("pong")
