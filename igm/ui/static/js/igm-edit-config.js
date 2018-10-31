const getNestedObject = (nestedObj, pathArr) => {
    return pathArr.reduce((obj, key) =>
        (obj && obj[key] !== 'undefined') ? obj[key] : undefined, nestedObj);
}

const setNestedObject = (nestedObj, pathArr, value) => {
  var k = pathArr.shift();
  if (pathArr.length == 0) {
    nestedObj[k] = value;
  } else {
    if ( nestedObj[k] === undefined )
      nestedObj[k] = {};
    setNestedObject(nestedObj[k], pathArr, value);
  }
}

function namesToPaths(data, path, obj) {

  if ( obj === undefined ) {
    obj = {};
  }

  if ( data !== null &&
       typeof data === 'object' &&
       Array.isArray(data) === false ) {

    $.each(data, (key, value) => {

      var p = path === "" ? key : path + '__' + key;
      namesToPaths(value, p, obj);

    });

  } else {

      obj[path] = data;

  }

  return obj;

}

function randomInt(max) {
  return Math.floor(Math.random() * Math.floor(max));
}

function ConfigUI(root_element, schema, current_cfg) {

  self = this;
  self.schema = schema;
  self.root = root_element;
  self.dependencies = [];
  self.inputs = {};
  self.groups = {};
  self.optional_groups = {}
  self.defaults = {}
  self.optpaths = [];

  self.parseItem = function(item, el, path, level, item_id){

    // if the item has a label, it is a group or a variable
    if ( item.label === undefined ) {

      return;

    }

    var curr_path = '';
    if ( path )
      curr_path += path + '__';
    if ( item_id )
      curr_path += item_id;

    if ( item.role && item.role == 'optional-group' ) {
      // handle optional groups
      self.optpaths.push(curr_path);
      var div = $(`<div id="grp-${curr_path}" class="igm-group igm-optional-group igm-group-${level}"></div>`);
      var checkdiv = $('<div></div>');
      div.append(checkdiv);
      var label = $(`<label><h${level}> ${item.label} </h${level}></label>`);
      var checkbox = $(`<input type="checkbox" class="igm-opt-grp-checkbox" name="${curr_path}"></input>`);
//      if ( current_cfg !== undefined &&
//           getNestedObject(current_cfg, curr_path.split('__')) !== undefined )
//        checkbox.prop('checked', true);
      checkbox.prop('checked', false); // optional are not selected by default
      var inner_div = $('<div class="igm-optional-group-inner"></div>');

      checkbox.on('change', () => inner_div.toggle(checkbox.prop('checked')));

      checkdiv.append(checkbox);
      checkdiv.append(label);

      if ( item.description ) {
        var description = $('<a class="igm-description"> (?)</a>');
        description.attr("title", item.description || "" );
        description.attr("ref-title", item.label );
        description.attr("item-id", item_id );
        label.append(description);
      }

      div.append(inner_div);
      inner_div.toggle(checkbox.prop('checked'));
      // iterate on all children
      $.each(item, function(key, value) {
        self.parseItem(value, inner_div, curr_path, level+1, key);
      });

      el.append(div);
      if ( item.depends_on !== undefined ) {
        self.dependencies.push( [ div, item.depends_on ] );
      }
      self.groups[ curr_path || 'root' ] = div;
      self.optional_groups[ curr_path || 'root' ] = div;

    } else if ( item.role && item.role == 'group' ) {
      // handle normal groups - only labels

      var div = $(`<div id="grp-${curr_path}" class="igm-group igm-group-${level}"></div>`);
      var label = $(`<h${level}> ${item.label} </h${level}>`);

      var inner_div = $('<div class="igm-group-inner"></div>');

      div.append(label);

      if ( item.description ) {
        var description = $('<a class="igm-description"> (?)</a>');
        description.attr("title", item.description || "" );
        description.attr("ref-title", item.label );
        description.attr("item-id", item_id );
        label.append(description);
      }

      div.append(inner_div);

      // iterate on all children
      $.each(item, function(key, value) {
        self.parseItem(value, inner_div, curr_path, level+1, key);
      })

      el.append(div);
      if ( item.depends_on !== undefined ) {
        self.dependencies.push( [ div, item.depends_on ] );
      }
      self.groups[ curr_path || 'root' ] = div;

    } else {
      // handle key/values
      setNestedObject( self.defaults, curr_path.split('__'), item.default );

      var div = $('<div class="igm-option"></div>');

      var label = $('<label>' + item.label + '</label>');

      if ( item.description ) {
        var description = $('<a class="igm-description"> (?)</a>');
        description.attr("title", item.description || "" );
        description.attr("ref-title", item.label );
        description.attr("item-id", item_id );
        label.append(description);
      }

      div.append(label);

      if ( item.depends_on !== undefined ) {
        self.dependencies.push( [ div, item.depends_on ] );
      }

      var input = undefined;

      // select input
      if ( item.allowed_values !== undefined ) {
        input = $(`<select name="${curr_path}"></select>`);
        $.each( item.allowed_values, function(index, value) {
          input.append( $(`<option value="${value}">${value}</option>`) );
        });
        input.val(item.default);
      }

      // int input
      else if ( item.dtype == 'int' ) {

        input = $(`<input type="number" step="1" name="${curr_path}"></input>`);
        var defval = item.default;
        if (item.default === '_random') {
          defval = randomInt(100000);
          rollel = $('<a href="javascript:void(0);"> [roll] </a>');
          rollel.click(() => { $(`[name=${curr_path}]`).val(randomInt(100000)); })
          label.append(rollel);
        }
        if ( item.min !== undefined )
          input.attr('min', item.min);
        if ( item.max !== undefined )
          input.attr('max', item.max);
        if ( item.default !== undefined )
          input.attr('value', defval)

      }

      // float input
      else if ( item.dtype == 'float' ) {

        input = $(`<input type="number" step="any" name="${curr_path}"></input>`);
        if ( item.min !== undefined )
          input.attr('min', item.min);
        if ( item.max !== undefined )
          input.attr('max', item.max);
        if ( item.default !== undefined )
          input.attr('value', item.default);

      }

      // path input
      else if ( item.dtype == 'path' || item.dtype == 'path-dir') {

        input = $(`<input type="text" name="${curr_path}"></input>`);
        if ( item.default !== undefined )
          input.attr('value', item.default);

      }

      // str input
      else if ( item.dtype == 'str' || Array.isArray( item.dtype ) ) {

        input = $(`<input type="text" name="${curr_path}"></input>`);
        if ( item.default !== undefined ){

          var v = typeof item.default == "string" ? item.default : JSON.stringify(item.default);
          input.val(v);

        }

      }

      // list input
      else if ( item.dtype == 'list' ) {

        var v = JSON.stringify(item.default).replace(/,/g, ', ');
        input = $(`<input type="text" class="igm-list-edit" name="${curr_path}"></input>`);
        input.val(v);
      }

      // array input
      else if ( item.dtype == 'array' ) {

        input = $(`<div class="igm-array-edit" name="${curr_path}"></div>`);

        var sublabels = item.sublabels || new Array(item.length);
        var defaults = item.default || new Array(item.length);
        for (var i = 0; i < item.length; i++) {
          input.append( $(`<label for="${curr_path}-${i}">${sublabels[i]}</label>`) );
          input.append( $(`<input type="text" id="${curr_path}-${i}" name="${curr_path}-${i}"
                            class="igm-array-el" value="${defaults[i]}"></input>`) );
        }

      }

      // bool input
      else if ( item.dtype == 'bool' ) {

        checked = item.default ? "checked" : "" ;
        input = $(`<input type="checkbox" name="${curr_path}" ${checked}></input>`);

      }

      div.append(input);
      self.inputs[curr_path] = input;

    }

    el.append(div);

  }

  self.setDependencies = function() {
    for (var i = 0; i < self.dependencies.length; i++) {
      var y = self.dependencies[i][0];
      var depVals = self.dependencies[i][1].split('=');
      var x = self.inputs[ depVals[0] ];
      var f = function(x, y, v){
        if ( x.val() == v ) {
          y.show();
        } else {
          y.hide();
        }
      };
      var k = f.bind(null, x, y, depVals[1]);
      k();
      x.on('change', k);
    }
  }


  self.update = function(current_cfg) {
    // reset to default
    if (current_cfg !== self.defaults)
        self.update(self.defaults);

    if (current_cfg) {

      // update with new values
      var paths = namesToPaths(current_cfg, '');

      $.each( paths, function(key, value) {

          el = $( `[name=${key}]` );
          if ( el.is(':checkbox') ) {
              el.prop('checked', value);
          } else if ( el.hasClass('igm-array-edit') ) {
            // fixed array edits have sub-edits
            for (var i = 0; i < value.length; i++) {
              sel = el = $( '#' + key + '-' + i);
              sel.val(value[i])
            }
          } else {
            // normal edits
            if ( value === undefined )
              value = "";
            el.val(typeof value === "string" ? value : JSON.stringify(value).replace(/,/g, ', '));
          }

      });

      // fix optional groups visibility
      $.each(self.optpaths, function(idx, optpath) {
        var isInConfig = false;
        $.each(paths, function(path, value){
          if (path.startsWith(optpath)) {
            isInConfig = true;
            return false;
          }
        });
        $( `[name=${optpath}]` ).prop('checked', isInConfig).trigger('change');
      });

    }

    self.setDependencies();

  }

  self.walkInputs = function(item, path, level, item_id, output){

    if ( item.label === undefined )
      return;

    var curr_path = '';
    if ( path )
      curr_path += path + '__';
    if ( item_id )
      curr_path += item_id;

    if ( item.role && item.role == 'optional-group' ) {
      // handle optional groups
      var checkbox = $(`input[name=${curr_path}]`);
      if ( checkbox.is(':checked') ) {
        // iterate on all children
        $.each(item, function(key, value) {
          self.walkInputs(value, curr_path, level+1, key, output);
        });
      }

    } else if ( item.role && item.role == 'group' ) {

      var div = $(`div#grp-${curr_path}`);
      if ( div.is(':visible') ) {
        $.each(item, function(key, value) {
          self.walkInputs(value, curr_path, level+1, key, output);
        });
      }

    } else {

      if ( $(`[name=${curr_path}]`).is(':visible') || $(`[name=${curr_path}-0]`).is(':visible') ) {

        if ( item.dtype == 'array' ) {

          var value = [];
          for (var i = 0; i < item.length; i++) {
            value.push( $(`[name=${curr_path}-${i}]`).val() );
          }
          output[curr_path] = value;

        } else  if ( item.dtype == 'bool' ) {

          output[curr_path] = $(`[name=${curr_path}]`).is(':checked');

        } else {

          output[curr_path] = $(`[name=${curr_path}]`).val();

        }

      }

    }

  }

  self.getConfig = function() {

    var output = {};
    self.walkInputs(self.schema, '', 1, '', output);
    return output;

  }

  // prepare the ui
  self.parseItem(self.schema, self.root, '', 1, '');
  self.update(current_cfg);

}
