// deepcopy an object
function deepcopy(obj){
  return JSON.parse(JSON.stringify(obj));
}

// python style range
function range(start, end, increment) {
    var array = [];
    var current = start;

    increment = increment || 1;
    if (increment > 0) {
        while (current < end) {
            array.push(current);
            current += increment;
        }
    } else {
        while (current > end) {
            array.push(current);
            current += increment;
        }
    }
    return array;
}
