#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import re
from functools import partial

from .utils import to_bool


def to_string(x):
    return x


class Group:

    __slots__ = 'name', 'short_text', 'start_text', 'end_text'

    def __init__(self, name, short_text, start_text='', end_text=''):
        self.name, self.short_text = name, short_text.strip()
        self.start_text, self.end_text = start_text.strip(), end_text.strip()


class Option:

    __slots__ = 'name', 'group', 'long_text', 'option_type', 'defval_as_string', 'add_to_default', 'add_to_docs'

    def __init__(self, name, group, defval, option_type, long_text, add_to_default, add_to_docs):
        self.name, self.group = name, group
        self.long_text, self.option_type = long_text.strip(), option_type
        self.defval_as_string = defval
        self.add_to_default = add_to_default
        self.add_to_docs = add_to_docs


class Shortcut:

    __slots__ = 'name', 'group', 'key', 'action_def', 'short_text', 'long_text', 'add_to_default', 'add_to_docs'

    def __init__(self, name, group, key, action_def, short_text, long_text, add_to_default, add_to_docs):
        self.name, self.group, self.key, self.action_def = name, group, key, action_def
        self.short_text, self.long_text = short_text, long_text
        self.add_to_default = add_to_default
        self.add_to_docs = add_to_docs


def option(
    all_options,
    group,
    name,
    defval,
    long_text='',
    option_type=to_string,
    add_to_default=True,
    add_to_docs=True
):
    is_multiple = name.startswith('+')
    if is_multiple:
        name = name[1:]
    defval_type = type(defval)
    if defval_type is not str:
        if option_type is to_string:
            if defval_type is bool:
                option_type = to_bool
            else:
                option_type = defval_type
        if defval_type is bool:
            defval = 'yes' if defval else 'no'
        else:
            defval = str(defval)

    key = name
    if is_multiple:
        key = name + ' ' + defval.partition(' ')[0]
    ans = Option(name, group[0], defval, option_type, long_text, add_to_default, add_to_docs)
    all_options[key] = ans
    return ans


def shortcut(
    all_options,
    group,
    action_name,
    key,
    action_def,
    short_text,
    long_text='',
    add_to_default=True,
    add_to_docs=True
):
    ans = Shortcut(action_name, group[0], key, action_def, short_text, long_text, add_to_default, add_to_docs)
    key = 'sc-' + action_name
    all_options.setdefault(key, []).append(ans)
    return ans


def option_func(all_options, all_groups):
    all_groups = {k: Group(k, *v) for k, v in all_groups.items()}
    group = [None]

    def change_group(name):
        group[0] = all_groups[name]

    return partial(option, all_options, group), partial(shortcut, all_options, group), change_group, all_groups


def merged_opts(all_options, opt, i):
    yield opt
    for k in range(i + 1, len(all_options)):
        q = all_options[k]
        if not isinstance(q, Option):
            break
        if not q.long_text and q.add_to_docs:
            yield q
        else:
            break


def remove_markup(text):
    return re.sub(r':([a-zA-Z0-9]+):`(.+?)`', r'\2', text, flags=re.DOTALL)


def render_block(text):
    text = remove_markup(text)
    lines = text.splitlines()
    return '\n'.join('#: ' + line for line in lines)


def as_conf_file(all_options):
    ans = ['# vim:fileencoding=utf-8:ft=conf:foldmethod=marker', '']
    a = ans.append
    current_group = None
    num_open_folds = 0
    all_options = list(all_options)

    def render_group(group, is_shortcut):
        nonlocal num_open_folds
        if is_shortcut or '.' not in group.name:
            a('# ' + group.short_text + ' {{''{')
            num_open_folds += 1
        a('')
        if group.start_text:
            a(render_block(group.start_text))
            a('')

    def handle_group_end(group, new_group_name='', new_group_is_shortcut=False):
        nonlocal num_open_folds
        if group.end_text:
            a(''), a(group.end_text)
        is_subgroup = new_group_name.startswith(group.name + '.')
        if not is_subgroup and num_open_folds > 0:
            a('# }}''}'), a('')
            num_open_folds -= 1

    def handle_group(new_group, is_shortcut=False):
        nonlocal current_group
        if new_group is not current_group:
            if current_group:
                handle_group_end(current_group, new_group.name, is_shortcut)
            current_group = new_group
            render_group(current_group, is_shortcut)

    def handle_shortcut(shortcuts):
        handle_group(shortcuts[0].group, True)
        for sc in shortcuts:
            a('map {} {}'.format(sc.key, sc.action_def))
            if sc.long_text:
                a('')
                for line in sc.long_text.strip().splitlines():
                    a('#: ' + line)
                a('')

    def handle_option(opt):
        if not opt.long_text or not opt.add_to_docs:
            return
        handle_group(opt.group)
        mopts = list(merged_opts(all_options, opt, i))
        sz = max(len(x.name) for x in mopts)
        for mo in mopts:
            prefix = '' if mo.add_to_default else '# '
            a(('{}{:%ds} {}' % sz).format(prefix, mo.name, mo.defval_as_string))
        a('')
        a(render_block(opt.long_text))
        a('')

    for i, opt in enumerate(all_options):
        if isinstance(opt, Option):
            handle_option(opt)
        else:
            handle_shortcut(opt)

    if current_group:
        handle_group_end(current_group)
        while num_open_folds > 0:
            a('# }}''}')
            num_open_folds -= 1
    return ans