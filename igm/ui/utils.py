import numbers
from copy import deepcopy

def html_input(itype, name, label, description, **kwargs):
    html = []

    addopt = ' '.join([
        '{}="{}"'.format(k, v) for k, v in kwargs.items()
    ])

    html.append(
        '<label for="edt_{}">{}<br><small>{}</small></label>'.format(
            name,
            label,
            description
        )
    )

    html.append(
        '<input type="{}" name="{}" id="edt_{}" {} />'.format(
            itype,
            name,
            name,
            addopt
        )
    )  
    
    return '\n'.join(html)

def html_select(name, label, description, values, default):
    html = []

    html.append(
        '<label for="edt_{}">{}<br><small>{}</small></label>'.format(
            name,
            label,
            description
        )
    )

    html.append(
        '<select name="{}" id="sel_{}"/>'.format(
            name,
            name
        )
    )  
    
    for v in values:
        if v == default:
            sels = 'selected'
        else:
            sels = ''
        html.append(
            '<option value="{0}" {1}>{0}</option>'.format(v, sels)
        )

    html.append('</select>')
    
    return '\n'.join(html)




def walk_options_tree(options, level, basename, html):
    
    
    html.append(
        '<h{lvl}><a class="toggler" data-toggle="opt_grp_{basename}">{basename}</a></h{lvl}>'.format(
            lvl=level + 1,
            basename=basename
        )
    )

    html.append(
        '<div class="igm-opt-group igm-opt-group-{}" \
        id="opt_grp_{}">'.format(
            level,
            basename 
        ) 
    )


    for name in options:
        
        if isinstance(options[name], dict):
            subname = basename + '__' + name
            walk_options_tree(options[name], level+1, subname, html)
            
        else:
            
            

            ptype, default, label, description, addopt = options[name]
            eid = basename + '__' + name

            cbclass = ''
            if ptype == bool:
                cbclass = 'igm-opt-cb'
            html.append(
                '<div class="igm-opt-input {}" >'.format(cbclass)
            )
                
            if addopt is None: 
                addopt = {}

            if ptype == str:
                if 'values' in addopt:
                    html.append(
                        html_select(
                            name=eid,
                            label=label,
                            description=description,
                            values=addopt['values'],
                            default=default
                        )
                    )
                else:
                    html.append(
                        html_input(
                            itype='text',
                            name=eid,
                            label=label,
                            description=description,
                            placeholder=description,
                            value=default
                        )
                    )

            elif ptype == list or ptype == tuple:
                if 'num_fields' in addopt:
                    n = addopt['num_fields']
                    html.append(
                        '<div class="igm-opt-list">'
                    )
                    html.append(
                        '<label>{}<br><small>{}</small></label>'.format(
                            label,
                            description
                        )
                    )
                    for i in range(n):
                        html.append(
                            '<input type="{}" name="{}" id="edt_{}" {} />'.format(
                                'text',
                                eid + '__' + str(i), 
                                eid + '__' + str(i),
                                'value=' + str(default[i]),
                            )
                        )

                    html.append('</div>')
                
                else:
                    html.append(
                            html_input(
                            name=eid,
                            label=label,
                            description=description,
                            placeholder=description,
                            value=', '.join(default)
                        )
                    )

            elif ptype == bool:
                html.append(
                    html_input(
                        itype='checkbox',
                        name=eid,
                        label=label,
                        description=description,
                        value=default
                    )
                )

            elif ptype == int:
                html.append(
                    html_input(
                        itype='number',
                        step='1',
                        name=eid,
                        label=label,
                        description=description,
                        placeholder=description,
                        value=default
                    )
                ) 

            elif ptype == float:
                html.append(
                    html_input(
                        itype='number',
                        step='any',
                        name=eid,
                        label=label,
                        description=description,
                        placeholder=description,
                        value=default
                    )
                )

            html.append(
                '</div>'
            )

    html.append('</div>')
        
def generate_form(options):
    level = 1
    basename = 'igm'
    html = []
    walk_options_tree(options, level, basename, html)
    return '\n'.join(html)


def parse_post_config(default, post, prefix):
    out = {}
    for k, v in default.items():
        if isinstance(v, dict):
            out[k] = parse_post_config(v, post, prefix=prefix+'__'+k)
        else:
            itype = v[0]
            if itype == list or itype == tuple:
                n = v[4].get('num_fields', None)
                if n is not None:
                    out[k] = []
                    for i in range(n):
                        elkey = prefix + '__' + k + '__' + str(i)
                        out[k].append(post[elkey])
                    out[k] = itype(out[k])
                else:
                    elkey = prefix + '__' + k
                    ftype = v[4].get('type', str)
                    out[k] = itype([ftype(x) for x in post[elkey].split(',')])
            elif itype == bool:
                elkey = prefix + '__' + k
                out[k] = itype(post.get(elkey, 0))
            else:
                elkey = prefix + '__' + k
                out[k] = itype(post[elkey])
    return out



