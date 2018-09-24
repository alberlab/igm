

var Viewer = function(container, options){

  var self = this;

  var container, stats;

  var camera, controls, scene, renderer;

  var cross;

  self.tubeFlag = true;
  self.sphereFlag = false;

  var container = container;

  var options = options || {};
  var backgroundColor = options.color || 0xeeeeee;

  var tubeOptions = options.tubeOptions || {

    splineQuality: 10,
    tubeWidth: 0.2,

  };

  var splineOptions = options.splineOptions || {

    curveType: 'catmull',

  };

  self.materials = {
    transparent: new THREE.MeshLambertMaterial({
      color: 0xcccccc,
      opacity: 0.2,
      transparent: true,
    }),

    solid: new THREE.MeshLambertMaterial({
      color: 0x666666,
      side: THREE.DoubleSide,
      transparent: false,
      reflectivity: 0,
      envMap: null,
    }),

    highlight: new THREE.MeshLambertMaterial({
      color: 0xcc00cc,
      side: THREE.DoubleSide,
      transparent: false,
      reflectivity: 0,
      envMap: null,
    }),

    transparent_highlight: new THREE.MeshLambertMaterial({
      color: 0xcc00cc,
      opacity: 0.2,
      transparent: true,
    }),

  };


  camera = new THREE.PerspectiveCamera( 50, container.offsetWidth / container.offsetHeight, 1, 10000 );
  camera.position.z = 50;

  self.group = new THREE.Group();

   // lights

  var light = new THREE.DirectionalLight( 0xffffff, 1);
  light.position.set( 30, 30, 0);
  camera.add( light );
  var light = new THREE.DirectionalLight( 0xffffff, 1);
  light.position.set( -30, -30, 0);
  camera.add( light );

  //var light = new THREE.DirectionalLight( 0x002288 );
  //light.position.set( -1, -1, -1 );
  //scene.add( light );

  //var light = new THREE.AmbientLight( 0x222222 );
  //scene.add( light );

  controls = new THREE.TrackballControls( camera, container );

  controls.rotateSpeed = 5.0;
  controls.zoomSpeed = 10.2;
  controls.panSpeed = 0.8;

  controls.noZoom = false;
  controls.noPan = false;

  controls.staticMoving = true;
  controls.dynamicDampingFactor = 0.3;

  controls.keys = [ 65, 83, 68 ];


    // world

  scene = new THREE.Scene();
  scene.background = new THREE.Color( backgroundColor );
  scene.add(camera);
  scene.add(self.group);

  var env_material = new THREE.MeshLambertMaterial({
    color: 0xffffff,
    opacity: 0.2,
    transparent: true,
  });
  var envelope = new THREE.Mesh( new THREE.SphereBufferGeometry( 5000.0, 64, 64 ), env_material );
  scene.add(envelope)

  //scene.fog = new THREE.FogExp2( 0xcccccc, 0.002 );

  // renderer

  renderer = new THREE.WebGLRenderer( { antialias: true } );
  renderer.setPixelRatio( window.devicePixelRatio );
  renderer.setSize( container.offsetWidth, container.offsetHeight, false );

  container.appendChild( renderer.domElement );

  var Gradient = function () {

    var bc = [ [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1] ];
    var nc = bc.length - 1;
    var deltas = [];
    for (var i = 0; i < nc; i++) {
      deltas.push([
        bc[i+1][0] - bc[i][0],
        bc[i+1][1] - bc[i][1],
        bc[i+1][2] - bc[i][2],
      ]);
    }

    this.getColor = function( x ) {

      var i = Math.floor(x * nc);
      if ( i == nc ) i -= 1;
      var offs = x * nc - i;
      return new THREE.Color(
        bc[i][0] + deltas[i][0] * offs,
        bc[i][1] + deltas[i][1] * offs,
        bc[i][2] + deltas[i][2] * offs,
      );

    }

  }

  var gradient = new Gradient();


  self.fitCameraToObject = function ( object, offset ) {

    offset = offset || 1.25;

    const boundingBox = new THREE.Box3();

    // get bounding box of object - this will be used to setup controls and camera
    boundingBox.setFromObject( object );

    const center = new THREE.Vector3();
    boundingBox.getCenter(center);

    const size = new THREE.Vector3();
    boundingBox.getSize(size);

    // get the max side of the bounding box (fits to width OR height as needed )
    const maxDim = Math.max( size.x, size.y, size.z );
    const fov = camera.fov * ( Math.PI / 180 );
    let cameraZ = Math.abs( maxDim / 4 * Math.tan( fov * 2 ) );

    cameraZ *= offset; // zoom out a little so that objects don't fill the screen

    camera.position.z = cameraZ;

    const minZ = boundingBox.min.z;
    const cameraToFarEdge = ( minZ < 0 ) ? -minZ + cameraZ : cameraZ - minZ;

    camera.far = cameraToFarEdge * 3;
    camera.updateProjectionMatrix();

    if ( controls ) {

      // set camera to rotate around center of loaded object
      //controls.target = center;

      // prevent camera from zooming out far enough to create far plane cutoff
      controls.maxDistance = cameraToFarEdge * 2;

      //controls.saveState();

    } else {

        camera.lookAt( center )

    }

  }

  self.fitCameraToObject(envelope);

  function getAverageSpacing(points){

    var avdist = 0.0;
    for (var i = 0; i < points.length-1; ++i){

      avdist += points[i].distanceTo(points[i+1]);

    }
    return avdist/(points.length-1);

  }

  function crdToVec3s(coordinates){
    points = [];
    for (var i = 0; i < coordinates.length; ++i){

      var pos = coordinates[i];
      points.push(new THREE.Vector3( pos[0], pos[1], pos[2] ));

    }
    return points;
  }

  self.getCenter = function(points){

    var com = new THREE.Vector3(0, 0, 0);
    for (var i = 0; i < points.length; ++i)
      com.add(points[i]);
    return com.multiplyScalar(1.0/points.length);

  }


  self.onWindowResize = function() {

    camera.aspect = container.offsetWidth / container.offsetHeight;
    camera.updateProjectionMatrix();

    renderer.setSize( container.offsetWidth, container.offsetHeight );

    controls.handleResize();

    self.render();

  }

  self.animate = function() {

    requestAnimationFrame( self.animate );
    controls.update();

  }

  self.render = function() {

    renderer.render( scene, camera );

  }

  controls.addEventListener( 'change', self.render );
  window.addEventListener( 'resize', self.onWindowResize, false );


  self.render();
  self.animate();

  self.getSpline = function(coordinates, closed=false, curve_type='chordal', tension=0.5, splineFactor=3){

    var vecs = crdToVec3s(coordinates);
    var avedist = getAverageSpacing(vecs);
    var p = closed ? 0: 1;
    var numSplinePoints = (coordinates.length - p)*splineFactor;
    var splineWidth = avedist/16;

    var pipeSpline = new THREE.CatmullRomCurve3( vecs, closed, curve_type, tension );
    return pipeSpline

  }

  self.PartialSpline = function ( spline, start, end, length=1.0, scale=1.0) {

    THREE.Curve.call( this );
    this.scale = ( scale === undefined ) ? 1 : scale;
    this.spline = spline;
    this.start = start / length;
    this.end = end / length;
    this.range = this.end - this.start;

  }

  self.PartialSpline.prototype = Object.create( THREE.Curve.prototype );
  self.PartialSpline.prototype.constructor = self.PartialSpline;

  self.PartialSpline.prototype.getPoint = function ( t ) {

    return this.spline.getPoint( this.start + t*this.range ).multiplyScalar( this.scale );

  };

  self.scaleCoordinates = function(points, maxSpan){

    var bbox = new THREE.Box3().setFromPoints(points);
    var sizes = bbox.getSize();
    var maxDim = Math.max(sizes.x, sizes.y, sizes.z);
    var scale = maxSpan/maxDim;
    for (var i = 0; i < points.length; ++i){
      points[i].multiplyScalar(scale);

    }
  }


  self.drawTube = function(coordinates, chains, opts){

    var opts = opts || {};
    var palette = opts.palette || self.generatePalette( coordinates.length );

    for ( var i = 0; i < chains.length; i++ ) {

      var chain = chains[ i ];

      var material = new THREE.MeshLambertMaterial({color: palette[ chain ]});

      self.addTube( coordinates[ chain ], material, opts );

    }
    //self.fitCameraToObject(envelope);
    // x.material = new THREE.MeshLambertMaterial({vertexColors: THREE.FaceColors})
    //x.geometry.colorsNeedUpdate = true
//     for ( var i = 0; i < x.geometry.faces.length; i ++ ) {

//     x.geometry.faces[ i ].color.setRGB( Math.random(), Math.random(), Math.random());

// }
  }

  self.draw = self.drawTube;

  self.generatePalette = function( n ) {

    var offset = 0.01;
    var colors = [];

    for (var i = 0; i < n; i++)
      colors.push( gradient.getColor(offset + (0.618033988749895 * i) % 1)) ;

    return colors;

  }

  self.addTube = function(coordinates, material, opts) {

    var opts = opts || {};
    var curveType = opts.curveType || 'chordal';
    var tension = opts.tension || 0.5;

    var points = crdToVec3s(coordinates);
    var numPoints = coordinates.length - 1;

    var pipeSpline = new THREE.CatmullRomCurve3( points, false, curveType, tension );

    var tubeWidth = opts.tubeWidth || 0.1;
    var splineQuality = opts.splineQuality || 3;
    var range = opts.range || [0, numPoints];
    var splineWidth = opts.splineWidth || 1;
    var tubeQuality = opts.tubeQuality || 8;


    // get average distances to use for the tube width
    var avedist = getAverageSpacing(points);
    var currTube = new self.PartialSpline(pipeSpline, range[0], range[1], numPoints);
    var currNumPoints = Math.abs(range[1] - range[0]);

    var numSplinePoints = currNumPoints * splineQuality;
    var geometry = new THREE.TubeGeometry( currTube, numSplinePoints, tubeWidth*avedist, tubeQuality, false );
    var mesh = new THREE.Mesh( geometry, material );
    self.group.add(mesh);

  }

  self.newSphereGeom = function( center, radius, opts, matrix ) {

    var opts = opts || {};
    var widthSegments = opts.widthSegments || 10;
    var heightSegments = opts.heightSegments || 6;
    sphere = new THREE.SphereBufferGeometry( radius, widthSegments, heightSegments );
    matrix.makeTranslation(
      center[0],
      center[1],
      center[2]
    );
    return sphere.applyMatrix( matrix );

  }

  self.addSphere = function( center, radius, material, opts ) {

    var opts = opts || {};
    var widthSegments = opts.widthSegments || 12;
    var heightSegments = opts.heightSegments || 12;
    sphere = new THREE.Mesh( new THREE.SphereBufferGeometry( radius, widthSegments, heightSegments ), material );
    sphere.position.set( center[0], center[1], center[2] );
    self.group.add( sphere );

  }

  self.drawBalls = function(coordinates, radii, chains, opts){

    var chain = chain || -1;
    var opts = opts || {};
    var palette = opts.palette || self.generatePalette( coordinates.length );
    var matrix = new THREE.Matrix4();

    // for ( var i = 0; i < chains.length; i++ ) {

    //   var chain = chains[ i ];
    //   var material = new THREE.MeshLambertMaterial({color: palette[ chain ]});

    //   for (var j = 0; j < coordinates[ chain ].length; j++) {
    //     self.addSphere( coordinates[ chain ][ j ], radii[ chain ][ j ], material, opts );
    //   }

    // }

    for ( var i = 0; i < chains.length; i++ ) {

      var chain = chains[ i ];
      var material = new THREE.MeshLambertMaterial({color: palette[ chain ]});
      var spheres = new Array(coordinates[ chain ].length);
      for (var j = 0; j < coordinates[ chain ].length; j++) {
        spheres[ j ] = self.newSphereGeom( coordinates[ chain ][ j ], radii[ chain ][ j ], opts, matrix );
      }
      var geom = THREE.BufferGeometryUtils.mergeBufferGeometries( spheres );
      geom.computeBoundingSphere();
      var mesh = new THREE.Mesh( geom, material );
      self.group.add( mesh );
    }
    //self.fitCameraToObject(self.group);
    // x.material = new THREE.MeshLambertMaterial({vertexColors: THREE.FaceColors})
    //x.geometry.colorsNeedUpdate = true
//     for ( var i = 0; i < x.geometry.faces.length; i ++ ) {

//     x.geometry.faces[ i ].color.setRGB( Math.random(), Math.random(), Math.random());

// }
  }

/*
for (i = 0; i < numpoints; i++) { this.grid[i] = [];

  u = i / (numpoints - 1);

  pos = path.getPointAt(u);
  var posRadius = this.radius[Math.floor((this.radius.length - 1) * u)];

  tangent = tangents[i];
  normal = normals[i];
  binormal = binormals[i];

  for (j = 0; j < this.radialSegments; j++) {

      v = j / this.radialSegments * 2 * Math.PI;
      cx = -posRadius * Math.cos(v); // TODO: Hack: Negating it so it faces outside.
      cy = posRadius * Math.sin(v);

      pos2.copy(pos);
      pos2.x += cx * normal.x + cy * binormal.x;
      pos2.y += cx * normal.y + cy * binormal.y;
      pos2.z += cx * normal.z + cy * binormal.z;

      this.grid[i][j] = vert(pos2.x, pos2.y, pos2.z);

  }
}
*/

  self.clear = function(render=true){

    for ( var i=self.group.children.length -1 ; i >= 0; --i ){
      obj = self.group.children[i];
      self.group.remove(obj);
    }
    if ( render )
      self.render();

  }

  self.redraw = function( status ) {

    self.clear(false);

    if ( ! status.num_beads ) {

      console.log('No beads to draw');
      return false;

    }
    // stack annotations

    if ( self.tubeFlag ) {

      self.drawTube( status.coordinates, status.current_chains, {
        palette: status.palette,
      });

    }

    if ( self.sphereFlag ) {

      self.drawBalls( status.coordinates, status.rad, status.current_chains, {
        palette: status.palette,
      });

    }

    self.render();

  }



  this.scene = function(){return scene;}
  this.renderer = function(){return renderer;}
  this.camera = function(){return camera;}
  this.controls = function(){return controls;}


  self.onWindowResize();
}
