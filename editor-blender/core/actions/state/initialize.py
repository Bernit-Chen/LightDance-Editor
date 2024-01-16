import asyncio
from typing import Dict, List, Optional

from ....api.auth_agent import auth_agent
from ....api.color_agent import color_agent
from ....api.dancer_agent import dancer_agent
from ....client import client
from ....client.subscription import subscribe
from ....core.asyncio import AsyncTask
from ....core.utils.get_data import get_control, get_pos
from ....core.utils.ui import redraw_area
from ....handlers import mount
from ....storage import get_storage
from ...models import (
    DancerPartIndexMap,
    DancerPartIndexMapItem,
    Dancers,
    LEDPartLengthMap,
    PartName,
    PartType,
    PartTypeMap,
    Selected,
    SelectedItem,
)
from ...states import state
from ..state.load import load_data


async def init_blender():
    # Open clients with token
    token: str = get_storage("token")
    state.token = token

    await client.open_http()

    # Check token
    token_valid = await auth_agent.check_token()
    if token_valid:
        state.is_logged_in = True
        state.is_running = True
        redraw_area("VIEW_3D")

        await client.open_graphql()

        if state.subscription_task is not None:
            state.subscription_task.cancel()
        state.subscription_task = AsyncTask(subscribe).exec()

        # Initialize editor
        if state.init_editor_task is not None:
            state.init_editor_task.cancel()
        state.init_editor_task = AsyncTask(init_editor).exec()

        mount()

    else:
        state.is_running = True
        redraw_area("VIEW_3D")


async def init_editor():
    empty_task = asyncio.create_task(asyncio.sleep(0))

    batches_functions = [
        [load_data, init_dancers, init_color_map],
        [init_current_status, init_current_pos],
        # [init_current_status, init_current_pos, init_current_led_status, sync_led_effect_record],
        # [sync_current_led_status],
    ]
    batches_completes = [[False] * len(batch) for batch in batches_functions]

    while True:
        try:
            for batch in range(len(batches_functions)):
                batch_functions = batches_functions[batch]
                batch_completes = batches_completes[batch]
                batch_tasks: List[asyncio.Task[Optional[BaseException]]] = [
                    empty_task
                ] * len(batch_functions)

                for index, function in enumerate(batch_functions):
                    if not batch_completes[index]:
                        batch_tasks[index] = asyncio.create_task(function())

                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )

                batch_done = True
                for index, result in enumerate(batch_results):
                    if isinstance(result, BaseException):
                        batch_done = False
                    else:
                        batch_completes[index] = True

                if not batch_done:
                    raise Exception(f"Batch {batch} failed")

            break
        except:
            pass

        await asyncio.sleep(1)

    print("Editor initialized")

    state.ready = True
    redraw_area("VIEW_3D")


async def init_dancers():
    dancers_array = await dancer_agent.get_dancers()

    dancer_names = [dancer.name for dancer in dancers_array]
    dancers: Dancers = dict(
        [
            (dancer.name, [part.name for part in dancer.parts])
            for dancer in dancers_array
        ]
    )

    part_type_map: PartTypeMap = {}
    led_part_length_map: LEDPartLengthMap = {}

    for dancer in dancers_array:
        for part in dancer.parts:
            part_type_map[part.name] = part.type
            if part.type == PartType.LED and part.length is not None:
                led_part_length_map[part.name] = part.length

    dancer_part_index_map: DancerPartIndexMap = {}

    for index, dancer in enumerate(dancers_array):
        parts: Dict[PartName, int] = dict(
            [(part.name, part_index) for part_index, part in enumerate(dancer.parts)]
        )
        dancer_part_index_map[dancer.name] = DancerPartIndexMapItem(
            index=index, parts=parts
        )

    selected: Selected = dict(
        [
            (dancer_name, SelectedItem(selected=False, parts=[]))
            for dancer_name in dancer_names
        ]
    )

    state.dancers = dancers
    state.dancer_names = dancer_names
    state.part_type_map = part_type_map
    state.led_part_length_map = led_part_length_map

    state.dancers_array = dancers_array
    state.dancer_part_index_map = dancer_part_index_map

    state.selected = selected

    print("Dancers initialized")


async def init_color_map():
    color_map = await color_agent.get_color_map()

    state.color_map = color_map

    print("Color map initialized")


async def init_current_status():
    control_map, control_record = await get_control()

    state.current_status = control_map[control_record[0]].status
    # TODO: Push status stack


async def init_current_pos():
    pos_map, pos_record = await get_pos()

    state.current_pos = pos_map[pos_record[0]].pos
    # TODO: Push pos stack
