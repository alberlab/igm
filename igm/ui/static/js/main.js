
var cui = null;
var igm_log = null;
var updateLogFlag = true;
var last_running_status = null;
var running_status = 'no';
var step_history = null;
var updateRunningFlag = true;
var interfaceTimeout = 1000;
var historyTimeout = 20000;
var updateHomeFlag = true;

var barpalette = ["#024d98","#034c96","#054c95","#064b93","#074b92","#094a90","#0b4a8f","#0c498d","#0d498c","#0f488a","#114889","#124887","#144786","#154784","#174683","#184681","#194580","#1b457e","#1c447d","#1e447b","#1f447a","#214378","#234377","#244275","#264274","#274172","#294171","#2a406f","#2c406e","#2d3f6c","#2f3f6b","#303f69","#323e68","#333e66","#353d65","#363d63","#383c62","#393c60","#3b3b5f","#3c3b5d","#3e3b5c","#3f3a5a","#413a59","#423957","#443956","#453854","#473853","#483751","#4a3750","#4b364e","#4d364d","#4e364b","#50354a","#513548","#533447","#543445","#563344","#573342","#593241","#5a323f","#5c313e","#5d313c","#5f313b","#603039","#613038","#632f36","#652f35","#662e33","#672e32","#692d30","#6b2d2f","#6c2d2d","#6e2c2c","#6f2c2a","#712b29","#722b27","#742a26","#752a24","#772923","#782921","#7a2820","#7b281e","#7d281d","#7e271b","#80271a","#812618","#832617","#842515","#862514","#872412","#892411","#8a240f","#8c230e","#8d230c","#8f220b","#902209","#922108","#932106","#952005","#962003","#981f02"];

function requestStart() {

  $('#btn-start-pipeline').off('click').text('Requesting...').attr('disabled', true);
  $.ajax({
    url : '/ajax/',
    method : 'POST',
    data : {
      'data' : JSON.stringify({ request : 'start_pipeline' })
    },
    dataType: 'json',
    success: (data) => {
      if (data.status != 'ok') {
        alert('An error occurred');
      }
    },
    error: (x, e, s) => { console.log(x, e, s); }
  });

}

function requestKill() {
  $('#btn-stop-pipeline').off('click').text('Requesting...').attr('disabled', true);
  $.ajax({
    url : '/ajax/',
    method : 'POST',
    data : {
      'data' : JSON.stringify({ request : 'kill_pipeline' })
    },
    dataType: 'json',
    success: (data) => {
      if (data.status != 'ok') {
        $('#btn-stop-pipeline').click(requestKill);
        alert('An error occurred');
      }
    },
    error: (x, e, s) => {
      $('#btn-stop-pipeline').click(requestKill);
      console.log(x, e, s);
      alert('An error occurred');
    }
  });
}

function getLog() {

  if (!updateLogFlag) {
    return;
  }

  $.ajax({
    url : '/ajax/',
    method : 'POST',
    data : {
      'data' : JSON.stringify({ request : 'get_log' })
    },
    dataType: 'json',
    success: (data) => { igm_log = data.log; },
    error: (x, e, s) => { console.log(x, e, s); }
  });

};


// ---- home status updates
function updateRunningStatus() {
  if (!updateRunningFlag) {
    return;
  }

  $.ajax({
    url : '/ajax/',
    method : 'POST',
    data : {
      'data' : JSON.stringify({ request : 'is_running' })
    },
    dataType: 'json',
    success: (data) => { running_status = data.status; },
    error: (x, e, s) => { console.log(x, e, s); }
  });
}

// ---- history updates
function updateHistory() {
  $.ajax({
    url : '/ajax/',
    method : 'POST',
    data : {
      'data' : JSON.stringify({ request : 'get_history' })
    },
    dataType: 'json',
    success: (data) => { step_history = data.history; },
    error: (x, e, s) => { console.log(x, e, s); }
  });
}


// ---- update the log view
function updateLogView() {
  updateLogFlag = $('#log-ta').is(":visible");
  if (updateLogFlag)
    $('#log-ta').val(igm_log);
}

function pad(num, size) {
    var s = num+"";
    while (s.length < size) s = "0" + s;
    return s;
}

function prettyTime( n ){

  var v = parseInt(n);
  var x = v % 60;
  var out = pad(x, 2) + 's';
  v = Math.floor( v / 60 );

  var units = ['m', 'h', 'd'];
  var step = [60, 60, 24];

  if ( v > 0 ) {
    for (var i = 0; i < units.length; i++) {
      var x = v % step[i];
      v = Math.floor( v / step[i] );
      if ( v > 0 )
        out = pad(x, 2) + units[i] + '&nbsp;' + out;
      else {
        out = x + units[i] + '&nbsp;' + out;
        break;
      }
    }
  }
  return out;

}

function updateHome(){
  if (!updateHomeFlag)
    return;
  // -------- configuration view
  if ( ! current_cfg ) {
    $('#config-status').html(`
      <div class="text-warning">
        No configuration file found in the current directory.
        <a href="#" id="opts-show-link"> Set a configuration file </a>
      </div>
    `);
    //opts-show-link
    $('#opts-show-link').off('click').click( () => $('#options-tab').tab('show') );


  } else {
    $('#config-status').html(`
      <div class="text-success">
        Configuration file: igm-config.json.
        <a href="#" id="opts-show-link"> Change configuration </a>
      </div>
    `);
    $('#opts-show-link').off('click').click( () => $('#options-tab').tab('show') );
  }

  // ---- running status view
  if ( ! current_cfg ) {
    $('#running-status').html('');
  } else if ( running_status != last_running_status ) {

    last_running_status = running_status;
    if ( running_status == 'no' ) {
      $('#running-status').html(`
        <div class="text-secondary">
          IGM is not currently running.
          <button class="btn btn-primary" id="btn-start-pipeline"> Start pipeline </button>
        </div>
      `);
      $('#btn-start-pipeline').click(requestStart);
    } else if ( running_status == 'maybe' ) {
      $('#running-status').html(`
        <div class="text-warning">
          IGM seems to be running, but not on this machine. If you are positive IGM is not
          currently running, you can
          <a id="btn-delete-processfile"> delete the process file </a>.
        </div>
      `);
    } else if ( running_status == 'yes' ) {
      $('#running-status').html(`
        <div class="text-primary">
          IGM is running.
          <a class="text-danger" id="btn-stop-pipeline" href="javascript:requestKill();"> Kill the process </a>
        </div>
      `);
    } else {
      $('#running-status').html('Error determining IGM status');
    }

  }

  // ---- history view
  if ( step_history && step_history.length) {
    var used = [];
    var cumulative = [];
    var max_used = 0;
    var tot_time = 0;
    var last_time = step_history[0].time;
    var groups = [];
    var last_name = '';
    for (var i = 0; i < step_history.length; i++) {
      if (step_history[i].name != last_name) {
        groups.push([i]);
      } else {
        groups[ groups.length - 1 ].push(i);
      }

      var u = (step_history[i].time - last_time).toFixed(0);
      used.push( u );
      max_used = Math.max(max_used, u);

      tot_time = Number(tot_time) + Number(u);
      cumulative.push( Number(tot_time) );

      last_time = step_history[i].time;
      last_name = step_history[i].name;
    }
    thead = `<thead><th>Step</th><th>Status</th><th colspan=2>Time</th><th  colspan=2>Cumulative time</th></thead>`;
    tbody = '<tbody>';
    for (var g = 0; g < groups.length; g++) {
      for (var gi = 0; gi < groups[g].length; gi++) {
        tbody += '<tr>';
        var i = groups[g][gi];
        if (gi == 0) {
          tbody += `<td rowspan=${groups[g].length}>${step_history[i].name}</td>`;
        }

        tbody += `<td>${step_history[i].status}</td>`;
        tbody += `<td class="text-right">${prettyTime(used[i])}</td>`;
        var uperc = (used[i] / max_used * 100).toFixed(1);
        tbody += `<td style="min-width: 100px !important;"><div class="progress-bar" fill="${uperc}" style="width : ${uperc}% ;">&nbsp;</div></td>`;

        tbody += `<td>${prettyTime(cumulative[i])}</td>`;
        var cperc = (cumulative[i] / tot_time * 100).toFixed(1);
        tbody += `<td style="min-width: 100px !important;"><div class="progress-bar" fill="${cperc}" style="width : ${cperc}%;">&nbsp;</div></td>`;
        tbody += '</tr>';
      }
    }

    $('#step-history').html('<table class="table table-sm">'+ thead + tbody + '</table>');
    $('.progress-bar').each( function(i, b) {
      $( this ).css('background-color',
        barpalette[ Math.floor( $( this ).attr('fill') ) ]
      );
    });

  } else {

    $('#step-history').html('<div class="alert alert-warning"> No history yet </div>');

  }

}

$(document).ready( function() {

    var bs = $("#bottom-spacer");

    // create the form controls
    cui = new ConfigUI($('#cfg-form-content'), schema);

    // give form controls Bootstrap look
    $.each( $('.igm-option'), function(i, item){
         $(item).addClass('form-group');
    });
    $.each( $('input:not(:checkbox), select'), function(i, item){
        $(item).addClass('form-control');
    });

    // fix checkboxes position
    $.each( $('input:checkbox'), function(i, item){

      $(item).parent().removeClass('form-group').addClass('form-check');
      if ( $(item).parent().hasClass('igm-option') )
        $(item).after( $( 'label', $(item).parent() ) );
      $(item).addClass('form-check-input');

    });

    // bind save on button

    const showAlerts = (errors, warnings) => {
      var html = '';
      for (var i = 0; i < errors.length; i++) {
        html += `<div class="alert alert-danger" role="alert">ERROR: ${errors[i]}</div>`;
      }

      for (var i = 0; i < warnings.length; i++) {
        html += `<div class="alert alert-warning" role="alert">WARNING: ${warnings[i]}</div>`;
      }

      $('#help-content').html(html);
      $('#help-wrapper').show();
      bs.height( $('#help-wrapper').height() + 20 );

      $("html, body").animate({ scrollTop: $(document).height() }, "slow");
    }

    $('button#btn-save-cfg').on('click', function(){

      const onSuccess = (data) => {
        current_cfg = data['cfg'];
        $('button#btn-save-cfg')
          .text('Saved!')
          .removeClass('btn-primary')
          .addClass('btn-success');

        showAlerts(data['errors'], data['warnings']);

        setTimeout(() =>
          $('button#btn-save-cfg')
            .text('Save')
            .removeClass('btn-success')
            .addClass('btn-primary'),
          10000);

      }

      const onFail = (data) => {

        $('button#btn-save-cfg')
          .text('Failed')
          .removeClass('btn-primary')
          .addClass('btn-danger');

        showAlerts(data['errors'], data['warnings']);

         setTimeout(() =>
          $('button#btn-save-cfg')
            .text('Save')
            .removeClass('btn-danger')
            .addClass('btn-primary'),
          10000);
      }

      $.ajax({

        url : '/ajax/',
        method : 'POST',
        dataType : 'json',
        data : {
          'data' : JSON.stringify({
            request : 'save_cfg',
            cfgdata : cui.getConfig()
          })
        },

        success : (data) => {
          console.log(data);
          if ( data.status == 'ok' )
            onSuccess(data);
          else
            onFail(data);
        },

        error : (x, e, v) => console.log(x, e, v),

      });

    });



    // $.each( $('.cbclass > input'), function(i, item){
    //     $(item).addClass('form-check-input');
    // });
    // $.each( $('.cbclass > label'), function(i, item){
    //     $(item).addClass('form-check-label');
    // });


    // $.each( $('.toggler'), function(i, item){
    //     $(item).click( function (){

    //         $('#' + $(item).attr('data-toggle')).toggle('fast');
    //         var visible = $('#' + $(item).attr('data-toggle')).is(':visible');
    //         var prefix = '\u25BC';
    //         if (!visible) {
    //             prefix = "\u25BA";
    //         }
    //         $(item).text(prefix + ' ' + $(item).attr('data-cleantxt'))

    //     });
    //     var txt = $(item).text();
    //     txt = txt.substring(txt.lastIndexOf('__')).replace('__', '');
    //     $(item).attr('data-cleantxt', txt);
    //     var visible = $('#' + $(item).attr('data-toggle')).is(':visible');
    //     var prefix = '\u25BC';
    //     if (!visible) {
    //         prefix = "\u25BA";
    //     }
    //     $(item).text(prefix + ' ' + $(item).attr('data-cleantxt'))
    // });


    // ------- dragging and resizing of help bottom window
    var dragging = false;
    $('#dragbar').mousedown( function(e){
      e.preventDefault();
      dragging = true;
      var hc = $("#help-wrapper");

      $(document).mousemove(function(e){
        var wh = window.innerHeight;
        var viewportTop = $(window).scrollTop();
        var viewportBottom = viewportTop + wh;

        var h = viewportBottom - e.pageY+2;
        if (h > 80 && h < wh - 80) {
          hc.css("height", h);
          bs.css("height", h);
        }
      });

    });

    $(document).mouseup(function(e){
       if (dragging)
       {
           $(document).unbind('mousemove');
           dragging = false;
       }
    });

    $('#btn-help-close').click( () => { $('#help-wrapper').hide(); bs.height(20); } );

    // -------- clicking the question marks opens the description
    //          in the configuration view
    $('.igm-description').click( (e) => {
      var caller = $( e.target );
      var title = caller.attr('ref-title');
      var text = caller.attr('title');
      var item_id = caller.attr('item-id');
      $('#help-content').html(`
        <h4>${title} <small>(${item_id})</small></h4>
        <p>${text}</p>
      `);
      $('#help-wrapper').show();
      bs.height( $('#help-wrapper').height() + 20 );
    });

    // -------- the help window starts closed
    $('#help-wrapper').hide();

    const updateCfg = () => {
      $.ajax({
        url : '/ajax/',
        method : 'POST',
        data : { request : 'get_cfg' },
        dataType: 'json',
        success: (data) => { current_cfg = data }
      });
    };

  getLog();
  setInterval(getLog, interfaceTimeout);

  updateLogView();
  setInterval(updateLogView, interfaceTimeout);

  updateRunningStatus();
  setInterval(updateRunningStatus, interfaceTimeout);

  updateHistory();
  setInterval(updateHistory, historyTimeout);

  setInterval(updateHome, interfaceTimeout);

}); // document.ready

// ---- LOG stuff

