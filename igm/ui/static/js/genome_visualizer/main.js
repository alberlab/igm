var app = null;

$(document).ready(function() {

  // setup the app
  app = new GenomeApp();

  // actually disable links
  $(".toolbar-link.disabled").prop('disabled', true);

  //
  $("#bead-interval-invert").on("change", function() {

    app.changeBeadInterval();

  });

  $("#traj-next").on('click', function() {

    app.changeFrame( app.status.current_frame + 1 );

  });

  $("#traj-prev").on('click', function() {

    app.changeFrame( app.status.current_frame - 1 );

  });

  $("button#select-file-btn").click(function(){

    app.setFile($('#file-field').val());
    return false;

  });


  $('#chromosome-ctrl').on('change', function(){

    if ( $('#chromosome-ctrl').val() == "-1" ) {

      $('input[name=chain_select]').prop('checked', true);
      app.updateView({chain: -1});

    }

    else if ( $('#chromosome-ctrl').val() == "-2" ) {

      app.status.current_chains = [];
      $('input[name=chain_select]').prop('checked', false);

    }

    else {

      var ids = $('#chromosome-ctrl').val().split(',');
      for (var i = 0; i < ids.length; i++) {

        ids[ i ] = parseInt(ids[ i ]);

      }

      var cc = [];
      for (var i = 0; i < app.status.num_chains; i++) {
        if ( ids.indexOf(i) !== -1 ) {
          cc.push([i, true]);
          $('input#chain_select_' + i).prop('checked', true);
        } else {
          cc.push([i, false]);
          $('input#chain_select_' + i).prop('checked', false);
        }
      }

      app.updateView({chain: cc});

    }

  });

  $('#structure-select-ctrl').on('change', function(){

    app.changeFrame( parseInt( $('#structure-select-ctrl').val() ) - 1 );

  });

  $('#jobform').submit( function() {

    return false;

  });

  $('#tube-box').on('change', function(){

    app.updateView({

      tube: $('#tube-box').prop('checked')

    });

  });

  $('#sphere-box').on('change', function(){

    app.updateView({

      sphere: $('#sphere-box').prop('checked')

    });

  });

  app.fileBrowser = new FileBrowser('#file-browser', function(path) {

    app.setFile(path);
    return false;

  });

});
