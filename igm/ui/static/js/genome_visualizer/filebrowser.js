
function baseName(str)
{
   var base = new String(str).substring(str.lastIndexOf('/') + 1);
    // if(base.lastIndexOf(".") != -1)
    //     base = base.substring(0, base.lastIndexOf("."));
   return base;
}

var FileBrowser = function(dom_element, onFileSelect, root_path='') {

  var self = this;
  self.current_path = root_path;
  self.dom_element = $(dom_element);

  self.loading_div =  $('<div id="fb_u_loading"></div>');
  self.dom_element.append(self.loading_div);
  self.loading_div.hide();

  self.path_div = $('<div id="fb_u_path"></div>');
  self.dom_element.append(self.path_div);

  self.content_div = $('<div id="fb_u_content"></div>');
  self.dom_element.append(self.content_div);

  self.dom_element.append($('<div style="text-align:right"><a id="fb_u_reload_btn" href="#">update</a></div>'));

  self.updateView = function(path, dirs, files) {

    self.current_path = path;

    self.loading_div.hide();
    self.path_div.html('<span class="fb_c_label"></span><span class="fb_c_path">' + path + '</span>');

    var dirs_html = '<ul id="fb_u_dirs">'
    for (var i = 0; i < dirs.length; i++) {
      dirs_html += `<li class="fb_c_dir"><span class="fb_icon fb_dir_icon"><i class="far fa-folder"></i></span><a href="#" class="fb_l_dir" fb-target="${dirs[i]}">${ baseName( dirs[i] ) }</a></li>`;
    }
    dirs_html += '</ul>';

    var files_html = '<ul id="fb_u_files">'
    for (var i = 0; i < files.length; i++) {
      files_html += `<li class="fb_c_file"><span class="fb_icon fb_file_icon"><i class="far fa-file"></i></span><a href="#" class="fb_l_file" fb-target="${files[i]}">${ baseName( files[i] ) }</a></li>`;
    }
    files_html += '</ul>';

    self.content_div.html(dirs_html + files_html);

    $.each( self.content_div.find('.fb_l_dir'), function(index, item) {
      $(item).on( 'click', function() {
        self.navigate( $(item).attr('fb-target') );
      });
    });

    $.each( self.content_div.find('.fb_l_file'), function(index, item) {
      $(item).on( 'click', function() {
        onFileSelect( $(item).attr('fb-target') );
      });
    });

  }

  self.navigate = function(path) {
    self.loading_div.show();
    req = {
      request: 'listhss',
      path: self.current_path + '/' + path,
    };
    $.ajax({
      type: "POST",
      url: '/ajax/',
      data : {
        'data' : JSON.stringify(req)
      },
      dataType: 'json',
      success: function(data){
        self.updateView(data.path, data.dirs, data.files);
        self.current_path = data.path;
      },
      error: function(x, e, t){
        console.log(x,e,t);
        alert('error!');
      }
    });
  }

  self.navigate(root_path);

  $("#fb_u_reload_btn").click( function() {
    self.navigate(self.current_path);
  });

}
