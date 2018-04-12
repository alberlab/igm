import sys
import igm.ui.views as vw

with open('history.html', 'w') as f:
    f.write( vw.history( sys.argv[1] ) )