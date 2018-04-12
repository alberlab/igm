import tornado.ioloop
import tornado.web
import sys
from igm.ui.views import history

cfg = sys.argv[1]

if len(sys.argv)>2:
    port = int(sys.argv[2])
else:
    port = 43254

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(history(cfg))

if __name__ == "__main__":
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    application.listen(port)
    tornado.ioloop.IOLoop.current().start()