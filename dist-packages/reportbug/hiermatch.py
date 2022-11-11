# hiermatch - Doing match on a list of string or a hierarchy.
#   Written by Chris Lawrence <lawrencc@debian.org>
#   Copyright (C) 1999-2008 Chris Lawrence
#   Copyright (C) 2008-2022 Sandro Tosi <morph@debian.org>

import re
from . import exceptions


def egrep_list(strlist, pattern_str, subindex=None):
    """
    Use the pattern_str to find any match in a list of strings

    This is a helper function for :func:`egrep_hierarchy`.

    Note that this function is never called with the `subindex`
    parameter set.

    Parameters
    ----------
    strlist : [str, ...]
        list of strings in which to look for the pattern
    pattern_str : str
        regular expression pattern
    subindex : [int, ...]
        list of indexes of strings in strlist, specifying the elements
        in which to look for the pattern

    Returns
    -------
    [int, ...]
        a list of indexes for the matches in the origin list
    """
    if strlist is None:
        return None

    try:
        pat = re.compile(pattern_str, re.I | re.M)
    except Exception:
        raise exceptions.InvalidRegex

    resultlist = []
    if subindex is None:
        subindex = list(range(len(strlist)))
    for i in subindex:
        if pat.search(strlist[i]):
            resultlist.append(i)
    return resultlist


def egrep_hierarchy(hier, pattern_str, subhier=None, nth=1):
    """
    Grep the nth item of a hierarchy [(x, [a, b]),...]

    This is a helper function for :func:`matched_hierarchy`.

    Note that this function is never called with the `subhier` and `nth`
    parameters set.

    Parameters
    ----------
    hier : [(str, [str, ...]), (str, [str, ...]), ...]
        list of tuples with severity and bug list
    pattern_str : str
        regular expression pattern
    subhier : [[int, ...], ...], optional
        subhierarchy indices
    nth : int, optional
        should always be 1 (one)

    Returns
    -------
    [[int, ...], [int, ...], ...]
        a subhierarchy (for each severity in the input hierarchy, the
        list of indexes of the bugs matching the pattern_str)
    """
    resulthier = []

    for i in range(len(hier)):
        if subhier:
            if subhier[i]:  # Only if have something to match.
                resultlist = egrep_list(hier[i][nth], pattern_str, subhier[i])
            else:
                resultlist = []
        else:
            resultlist = egrep_list(hier[i][nth], pattern_str)

        resulthier.append(resultlist)
    return resulthier


def matched_hierarchy(hier, pattern_str):
    """
    Create a new hierarchy from a pattern matching

    Parameters
    ----------
    hier : [(str, [str, ...]), (str, [str, ...]), ...]
        list of tuples with severity and bug list
    pattern_str : str
        regular expression pattern

    Returns
    -------
    [(str, [str, ...]), (str, [str, ...]), ...]
        list of tuples with severity and bug list, only including bugs
        matching the pattern_str
    """
    mhier = []
    result = egrep_hierarchy(hier, pattern_str)
    for i in range(len(result)):
        if result[i]:
            item = [hier[i][1][y] for y in result[i]]
            mhier.append((hier[i][0], item))
    return mhier

# vim:ts=8:sw=4:expandtab:
