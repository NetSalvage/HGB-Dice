from decimal import Decimal, DecimalException
from itertools import chain
from typing import Dict, Mapping
from dearpygui.dearpygui import *
import HGBDiceStats as stats

PLOT_HEIGHT = 450
PLOT_WIDTH = 425
BAR_WIDTH = 0.8

test = Mapping[str, stats.Result]


def show_plots(show: Tuple[str], hide: Tuple[str]):
    def callback(sender, app_data):
        if app_data[0] != 0:  # left click only
            return
        nonlocal show, hide
        for plot in hide:
            hide_item(plot)
        for plot in show:
            show_item(plot)

    return callback


def skip_plot(result: stats.Result) -> bool:
    return (
        result.sources["All"].average == 0
        and len(result.sources["All"].totals) < 2
        and not stats.analyses[result.name].show_if_missing
    )


# TODO: Create and delete series/plots on demand within window
def graph_results(window: int, tests: Mapping[str, test]):
    push_container_stack(window)
    add_text("Click plots to cycle between analysis types!")
    # TODO: Add dropdown for comparisons
    # TODO: Recalc max cols for multiple tests
    # cols = max(len(res.get("by_source", [])) for res in test) + 1
    cols = 7  # TODO: See if this is even necessary
    with table(
        header_row=False,
        resizable=False,
        policy=mvTable_SizingFixedSame,
        borders_outerH=False,
        borders_outerV=False,
        borders_innerH=False,
        borders_innerV=True,
        scrollX=True,
        scrollY=True,
    ):
        for _ in range(cols):
            add_table_column(
                width=PLOT_WIDTH + 5,
                width_fixed=True,
                no_resize=True,
                no_reorder=True,
                no_sort=True,
            )
        analyses = chain.from_iterable(test.keys() for test in tests.values())
        analyses = list(dict.fromkeys(analyses))  # Deduplicate analysis names
        for analysis in analyses:
            # skip missing
            if all(skip_plot(test[analysis]) for test in tests.values()):
                continue
            base_plots, normal_plots, min_plots = plot_result(tests, analysis)

            base_handler = add_item_handler_registry()
            normal_handler = add_item_handler_registry()
            min_handler = add_item_handler_registry()

            if normal_plots:
                show = normal_plots
                hide = base_plots + min_plots
            elif min_plots:
                show = min_plots
                hide = base_plots + min_plots
            else:
                show = base_plots
                hide = tuple()

            add_item_clicked_handler(
                parent=base_handler,
                callback=show_plots(show, hide),
            )

            if min_plots:
                show = min_plots
                hide = base_plots + normal_plots
            else:
                show = base_plots
                hide = normal_plots
            add_item_clicked_handler(
                parent=normal_handler, callback=show_plots(show, hide)
            )

            add_item_clicked_handler(
                parent=min_handler,
                callback=show_plots(base_plots, normal_plots + min_plots),
            )

            for plot in base_plots:
                bind_item_handler_registry(plot, base_handler)
            for plot in normal_plots:
                bind_item_handler_registry(plot, normal_handler)
                hide_item(plot)
            for plot in min_plots:
                bind_item_handler_registry(plot, min_handler)
                hide_item(plot)

    pop_container_stack()


def plot_result(tests: Mapping[str, test], analysis: str) -> Tuple[Tuple[int]]:
    base_label = f"{analysis}"
    normal_label = f"WHEN {analysis} > 0"
    min_label = f"{analysis} AT LEAST X:"
    groups = []

    with table_row(height=PLOT_HEIGHT + 5):
        source_names = chain.from_iterable(
            test[analysis].sources for test in tests.values()
        )
        source_names = list(dict.fromkeys(source_names))  # Deduplicate source names

        if len(source_names) < 3:  # Don't make source plots if single source present
            source_names = ["All"]

        for source_name in source_names:
            results = {
                name: test[analysis].sources[source_name]
                for name, test in tests.items()
            }
            base_label = f"{analysis} from {source_name}"
            normal_label = f"WHEN {analysis} > 0:" + f"\n{analysis} from {source_name}"
            min_label = f"{analysis} AT LEAST X:" + f"\n{analysis} from {source_name}"
            groups.append(
                make_plot_group(results, (base_label, normal_label, min_label))
            )

    # transpose and return list of groups
    return tuple(tuple(p for p in g if p is not None) for g in zip(*groups))


def make_plot_group(
    results: Mapping[str, stats.SourceResult], labels: Tuple[str]
) -> Tuple[int]:
    base_label, normal_label, min_label = labels
    datatype = list(results.values())[0].type
    with table_cell():
        base_plot = bar_plot(
            label=base_label,
            height=PLOT_HEIGHT,
            width=PLOT_WIDTH,
            data_x=[[float(k) for k in result.totals] for result in results.values()],
            data_y=[
                [float(v) for v in result.totals.values()]
                for result in results.values()
            ],
            names=list(results),
            datatype=datatype,
        )
        normal_plot = None
        min_plot = None
        if datatype == stats.AnalysisType.RANGE:
            normal_plot = bar_plot(
                label=normal_label,
                height=PLOT_HEIGHT,
                width=PLOT_WIDTH,
                data_x=[
                    [float(k) for k in result.normalized_totals]
                    for result in results.values()
                ],
                data_y=[
                    [float(v) for v in result.normalized_totals.values()]
                    for result in results.values()
                ],
                names=list(results),
                datatype=datatype,
            )

            if any(result.min_totals for result in results.values()):
                min_plot = bar_plot(
                    label=min_label,
                    height=PLOT_HEIGHT,
                    width=PLOT_WIDTH,
                    data_x=[
                        [float(k) for k in result.min_totals]
                        for result in results.values()
                    ],
                    data_y=[
                        [float(v) for v in result.min_totals.values()]
                        for result in results.values()
                    ],
                    names=list(results),
                    datatype=datatype,
                    show_average=False,
                )

    return (base_plot, normal_plot, min_plot)


def bar_plot(
    label: str,
    height: int,
    width: int,
    data_x: List[List[float]],
    data_y: List[List[float]],
    names: List[str],
    datatype: stats.AnalysisType,
    show_average: bool = True,
) -> int:
    plot = add_plot(
        label=label,
        height=height,
        width=width,
        no_mouse_pos=True,
    )
    add_plot_legend(parent=plot)
    # Dummy missing data
    data_x = [x if x else [] for x in data_x]
    data_y = [y if y else [] for y in data_y]

    x_min = min(chain.from_iterable(data_x)) - 0.8
    x_max = max(chain.from_iterable(data_x)) + 0.8
    y_max = max(chain.from_iterable(data_y)) * 1.2

    x_axis = add_plot_axis(parent=plot, axis=mvXAxis)
    if datatype == stats.AnalysisType.BOOL:
        set_axis_ticks(x_axis, (("No", 0), ("Yes", 1)))
    elif datatype == stats.AnalysisType.RANGE:
        labels = [str(int(x)) for x in chain.from_iterable(data_x)]
        set_axis_ticks(x_axis, tuple(zip(labels, chain.from_iterable(data_x))))
    y_label = "Probability %"
    y_axis = add_plot_axis(parent=plot, axis=mvYAxis, label=y_label)
    labels = [f"{y:0.2%}" for y in chain.from_iterable(data_y)]
    set_axis_ticks(y_axis, tuple(zip(labels, chain.from_iterable(data_y))))

    for idx, (series_x, series_y, name) in enumerate(zip(data_x, data_y, names)):
        weight = BAR_WIDTH / len(data_y)
        left = (len(data_y) - 1) * -(weight / 2)
        offset = left + (idx * weight)
        avg = sum(x * y for x, y in zip(series_x, series_y))
        if datatype == stats.AnalysisType.BOOL:
            avg_label = f" (Avg: {avg:0.1%})"
        else:
            avg_label = f" (Avg: {avg:0.2f})"
        if not show_average:
            avg_label = ""
        add_bar_series(
            [x + offset for x in series_x],
            series_y,
            label=f"{name}{avg_label}",
            parent=y_axis,
            weight=weight,
        )
    set_axis_limits(x_axis, ymin=x_min, ymax=x_max)
    set_axis_limits(y_axis, ymin=0.0, ymax=y_max)

    return plot
