import sys,tempfile,socket,threading,time,urllib.request,gzip
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from backend.app import create_app
with tempfile.TemporaryDirectory() as directory:
    app=create_app(configuration_file=Path(directory)/'configurations.json')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
    worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);worker.start()
    deadline=time.monotonic()+15
    while not server.started and time.monotonic()<deadline:time.sleep(.02)
    def read(path,encoding=None):
        request=urllib.request.Request('http://127.0.0.1:'+str(port)+path,headers={'Accept-Encoding':encoding or 'identity'})
        with urllib.request.urlopen(request) as response:return response.headers,response.read()
    try:
        headers,html=read('/');assert headers['Cache-Control']=='no-store'
        assert html.index(b'js/ui/requests.js')<html.index(b'js/ui/library-sets.js')
        headers,plain=read('/js/ui/requests.js?v=test');assert 'immutable' in headers['Cache-Control']
        headers,compressed=read('/js/ui/requests.js?v=test','gzip');assert headers['Content-Encoding']=='gzip';assert gzip.decompress(compressed)==plain
        assert len(compressed)<len(plain)
        headers,_=read('/api/configurations');assert headers['Cache-Control']=='no-store'
        headers,api_plain=read('/api/equipment/team')
        headers,api_gzip=read('/api/equipment/team','gzip');assert headers['Cache-Control']=='no-store'
        assert headers['Content-Encoding']=='gzip' and gzip.decompress(api_gzip)==api_plain
        print('PASS: equipment API compressed bytes',len(api_plain),'->',len(api_gzip))
        headers,_=read('/js/ui/requests.js');assert headers['Cache-Control']=='no-store'
        print('PASS: HTML/API remain fresh; versioned assets cached; gzip bytes',len(plain),'->',len(compressed))
    finally:server.should_exit=True;worker.join(5);sock.close()
