__author__ = 'mike'

def acquisition_data(ax, mobj, dtype='mag', **plt_props):
    """
    Plots the down_field branch of a hysteresis
    """
    ax.plot(mobj.data['data']['window_mean'].v,
            mobj.data['data'][dtype].v,
            **plt_props)

def cumsum_acquisition_data(ax, mobj, dtype='mag', **plt_props):
    """
    Plots the down_field branch of a hysteresis
    """
    ax.plot(mobj.cumulative['window_mean'].v,
            mobj.cumulative[dtype].v,
            **plt_props)