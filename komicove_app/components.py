import threading
def background(root,work,done):
    def run():
        try: result,error=work(),None
        except Exception as exc: result,error=None,str(exc)
        root.after(0,lambda:done(result,error))
    threading.Thread(target=run,daemon=True).start()
