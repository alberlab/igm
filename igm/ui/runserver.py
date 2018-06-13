import tornado.ioloop
import tornado.web
import sys
import json
from igm.ui.views import history, config_form, config_form_process

if len(sys.argv) > 1:
    cfg = sys.argv[1]
else:
    cfg = None

if len(sys.argv)>2:
    port = int(sys.argv[2])
else:
    port = 43254

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        if cfg:
            self.write(history(cfg))

class CfgFormHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(config_form())

    def post(self):
        self.set_header("Content-Type", "text/plain")
        postdata = { k: self.get_argument(k) for k in self.request.arguments }
        cfg = config_form_process(postdata)
        self.write( json.dumps(cfg, indent=4) )

if __name__ == "__main__":
    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/configure/", CfgFormHandler)
    ])
    application.listen(port)
    tornado.ioloop.IOLoop.current().start()