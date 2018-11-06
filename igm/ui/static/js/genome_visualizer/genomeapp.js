
var GenomeApp = function(){

  var self = this;

  // set some constants

  // set the size for the viewer
  var el = $('#viewer');  //record the elem so you don't crawl the DOM everytime
  var bottom = el.offset().top + el.outerHeight(true);
  var height = $(window).height() - bottom;
  var container = document.getElementById('viewer')
  $(container).height(Math.round($(window).height()*0.8));

  // create the viewer with default options
  var viewer = new Viewer(container);

  // create the app status
  var status = {};

  var interface = new InterfaceControl(self);

  this.viewer = viewer;
  this.status = status;
  this.interface = interface;
  this.fileBrowser = null;

  var newFileFlag = false;


  // sets up the file loader

  var fileField = document.getElementById('file-field');

  function getCopies( chroms ) {

    var copies = {};
    copies.ordered_keys = [];

    for (var i = 0; i < chroms.length; i++) {

      var cname = chroms[i];

      if ( copies[cname] === undefined ) {

        copies[cname] = [ i ];
        copies.ordered_keys.push(cname);

      } else {

        copies[cname].push( i );

      }

    }

    return copies;

  }

  self.gotFileData = function(data) {

    if (data.status === 'failed') {
        alert('ERROR:\n' + data.reason);
        interface.activate();
        return false;
    }
    status.coordinates = data.crd;

    if (newFileFlag) {

      status.chroms = data.chroms;
      status.cstarts = data.cstarts;
      status.idx = data.idx;
      status.rad = data.rad;
      status.num_frames = data.n;
      status.num_beads = data.crd[0].length;
      status.num_chains = data.crd.length;
      status.copies = getCopies( status.chroms );
      status.num_chrom = status.copies.ordered_keys.length;
      status.current_chains = [];

      for (var i = 0; i < status.num_chains; i++) {
        status.current_chains.push(i);
      }

      var original_palette = viewer.generatePalette( status.num_chrom );
      status.palette = new Array(status.num_chains);

      for (var i = 0; i < status.num_chrom; i++) {
        var cname = status.copies.ordered_keys[i];
        var copies = status.copies[ cname ];
        var hsl = new THREE.Color();
        original_palette[ i ].getHSL(hsl);
        var offset = 1.0;
        for (var j = 0; j < copies.length; j++) {

          var chain = copies[ j ];
          var newhsl = { h: parseInt(hsl.h*360), s: parseInt(hsl.s*100.0), l: parseInt(hsl.l*offset*100.0) };
          status.palette[ chain ] = new THREE.Color(`hsl(${newhsl.h},${newhsl.s}%,${newhsl.l}%)`);

          offset *= 0.66;

        }

      }

      interface.setChains( status );


    }

    viewer.onWindowResize();
    viewer.redraw(status);
    interface.activate();
    interface.updateControls( status, 'traj' );



  }

  self.requestData = function(fname, i) {

    interface.deactivate();
    var req = {
      request: 'get_structure',
      path: fname,
      n : i
    };
    console.log(req)
    $.ajax({
      type: "POST",
      url: '/ajax/',
      data : {
        'data' : JSON.stringify(req)
      },
      success: self.gotFileData,
      dataType: 'json',
      error: function(x, err, et){

        console.log(x, err, et);
        interface.showLoad(false);
        interface.activate()
        interface.errorMessage('failed');

      },
    });

  }

  self.setFile = function(fname) {

    viewer.clear();
    status.current_frame = 0;
    status.current_chain = -1;
    newFileFlag = true;
    status.fname = fname;

    interface.showLoad(false);

    self.requestData(fname, 0);
    interface.updateControls(status, 'traj');

  }

  self.changeFrame = function( i ) {

    if ( i < 0 || i >= status.num_frames )
      return false;


    newFileFlag = false;

    viewer.clear();

    self.requestData(status.fname, i)

    status.current_frame = i;

    interface.updateControls(status, 'traj');

    //viewer.redraw(status, true);

  }

  self.changeChain = function( i ) {

    if ( i < 0 || i >= status.num_chains )
      return false;

    status.current_chain = i;

    interface.updateControls(status, 'all');

    viewer.redraw(status, true);

  }

  self.updateView = function(request) {

    interface.deactivate();

    if ( request.tube !== undefined )
      viewer.tubeFlag = request.tube;

    if ( request.sphere !== undefined )
      viewer.sphereFlag = request.sphere;

    if ( request.chain !== undefined ) {

      if ( request.chain === -1 ) {

        request.chain = [];
        for (var i = 0; i < status.num_chains; i++) {
          request.chain.push([i, true]);
        }

      }

      for (var i = 0; i < request.chain.length; i++) {

        var chain = request.chain[ i ][ 0 ];
        var visible = request.chain[ i ][ 1 ];
        var idx = status.current_chains.indexOf( chain );

        if ( visible && idx === -1 ) {
          status.current_chains.push( chain );
        }
        if ( !visible && idx !== -1 ) {
          status.current_chains.splice( idx, 1 );
        }

      }

    }

    viewer.redraw(status);
    interface.activate();

  }

}

