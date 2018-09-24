
var InterfaceControl = function(app) {

  var self = this;
  self.app = app;


  self.loadScreen = $('<div id="load-screen"></div>');
  self.loadScreen.append( $('<div class="transparent-background"></div>') );
  self.loadScreen.append( $('<span class="display-1"><i class="fas fa-spinner fa-spin"></i></span>') );

  $('#structure-visualizer-tab').append(self.loadScreen);
  self.loadScreen.hide();


  self.deactivate = function() {
    self.loadScreen.show()
    // disable all action while computing
    $("button#select-file-btn").prop('disabled', true);
    $("#download-link").off("click");
    $(".toolbar-link").prop('disabled', true);
    $(".toolbar-link:not(.disabled)").addClass('disabled');
    $("input, select").prop('disabled', true);
    $("#traj-next, #traj-prev").prop('disabled', true);

  }

  self.activate = function() {

    self.loadScreen.hide();
    $("button#select-file-btn").prop('disabled', false);
    $(".toolbar-link").prop('disabled', false);
    $('.nav-link.disabled').removeClass("disabled");
    $("input, select").prop('disabled', false);
    $("#traj-next, #traj-prev").prop('disabled', false);

  }

  self.updateControls = function(status, selector){


    // trajectory controls
    if ( selector === 'all' || selector === 'traj' ) {

      if ( status.num_frames > 1 )
        $('#trajectory-controls').show();
      else
        $('#trajectory-controls').hide();
      $('#traj-frame').html( 'Structure ' + ( status.current_frame + 1 ) + ' of ' + status.num_frames );

      $('#structure-select-ctrl').val( status.current_frame );
      $('#chromosome-ctrl').val( status.current_chain );

    }

  }


  self.clearMessageBoard = function() {
    $("#result-info").html("");
  }

  self.errorMessage = function(err, preformatted=false) {

    var ediv = '<div class="alert alert-danger" role="alert">'+ err + '</div>';
    var html = preformatted ? '<pre>'+ ediv + '</pre>' : ediv;
    $("#result-info").append(html);

  }

  self.infoMessage = function(msg, preformatted=false) {

    var ediv = '<div class="alert alert-info" role="alert">'+ msg + '</div>';
    var html = preformatted ? '<pre>'+ ediv + '</pre>' : ediv;
    $("#result-info").append(html);

  }


  self.setDownloadLink = function( data ) {

    var zip = new JSZip();
    zip.file("output.txt", data.result.out);
    zip.file("err.txt", data.result.err);
    zip.file("log.txt", data.result.log);

    $("#download-link").on("click", function () {

      zip.generateAsync( {type: "blob"} ).then( function ( blob ) { // 1) generate the zip file

          saveAs(blob, "results.zip");            // 2) trigger the download

      }, function (err) {

          self.errorMessage(err, true);

      });

    });

  }


  self.setLogs = function( data ) {

    var parmtxt = JSON.stringify( data.param, null, 2 );
    $('#log-prm').html( parmtxt );
    $('#log-cmd').html( data.cmd );
    $('#log-out').html( data.result.out );
    $('#log-err').html( data.result.err );

  }


  self.showLoad = function( yes=true ) {

    if (yes)
      $('#upload-dialog').modal('show');
    else
      $('#upload-dialog').modal('hide') ;

  }

  self.setChains = function( status ) {

    var chains = status.chroms;
    var palette = status.palette;
    var chrctrl = $('#chromosome-ctrl-div');
    var chromosomes = status.copies.ordered_keys;

    chrctrl.empty(); // remove old options

    var select = $('#chromosome-ctrl');
    select.empty(); // remove old options
    select.append($("<option></option>").attr("value", "-1")
                                        .text('-- all --'));

    for (var i = 0; i < chromosomes.length; i++) {

      select.append($("<option></option>").attr("value", status.copies[ chromosomes[ i ] ])
                                          .text(chromosomes[ i ]));

    }

    for (var i = 0; i < status.copies.ordered_keys.length; i++) {

      var cname = status.copies.ordered_keys[ i ];
      var copies = status.copies[ cname ];
      var inner_html = `<div class="col"><strong>${cname}</strong></div>`;

      for (var j = 0; j < copies.length; j++) {

        var chain = copies[ j ];
        var color = '#' + palette[ chain ].getHexString();

        inner_html += `
        <div class="col">
          <div class="form-check form-check-inline" style="border:solid 1px ${color};border-radius:2px;padding-left:3px;padding-right:3px;margin-left:1em">
            <label class="form-check-label">
              <input type="checkbox" id="chain_select_${chain}" name="chain_select" chain="${chain}" class="form-check-input" checked>
              copy ${j+1}
            </label>
          </div>
        </div>
        `;

      }

      chrctrl.append($("<div></div>").addClass("form-row").html(inner_html));

    }

    $('input[name=chain_select]').on('change', function(event) {

      var caller = $(event.target)

      var selected = caller.prop('checked');
      var chain_id = parseInt(caller.attr('chain'));

      self.app.updateView({

        chain: [ [chain_id, selected] ]

      });

    });

  }



}
