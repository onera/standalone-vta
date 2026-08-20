"""Regression tests for partitioned accumulator ALU operations."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


VTA_COMPILER_DIR = Path(__file__).parents[2] / "src" / "compiler" / "vta_compiler"
sys.path.insert(0, str(VTA_COMPILER_DIR))

from matrix_partitioning.alu_strategies import alu_strategy  # noqa: E402


VectorIndex = Tuple[int, int]


def _max_operation(destination: VectorIndex, source: VectorIndex) -> List[Any]:
    """Creates one lowered vector MAX operation.

    Args:
        destination: Destination block and row indices.
        source: Source block and row indices.

    Returns:
        Lowered ALU operation accepted by ``alu_strategy``.
    """
    return ["MAX", [[0, 0], [0, 0], 1], [(destination, [source])]]


def _execute_strategy(
    strategy: List[Tuple[Any, ...]],
    dram_values: Dict[VectorIndex, int],
) -> Dict[VectorIndex, int]:
    """Executes the strategy's scalar equivalent with persistent SRAM slots.

    Args:
        strategy: ALU partitioning strategy to evaluate.
        dram_values: Initial scalar value for every logical vector.

    Returns:
        Dense output values stored by the strategy.
    """
    sram: Dict[int, int] = {}
    output: Dict[VectorIndex, int] = {}

    for step in strategy:
        load_acc = step[2]
        sram_state = step[3]
        store_acc = step[5]
        operations = step[6]

        for vector in load_acc:
            sram[sram_state.index(vector)] = dram_values[vector]

        for operation in operations:
            destination, sources = operation[2][0]
            destination_slot = sram_state.index(destination)
            for source in sources:
                source_slot = sram_state.index(source)
                sram[destination_slot] = max(
                    sram[destination_slot], sram[source_slot]
                )

        for destination in store_acc:
            output[destination] = sram[sram_state.index(destination)]

    return output


def test_reduction_keeps_destination_in_a_stable_sram_slot() -> None:
    """A multi-step reduction must not renumber its live destination vector."""
    destination = (0, 0)
    sources = [(1, 0), (2, 0), (3, 0), (4, 0)]
    operations = [_max_operation(destination, source) for source in sources]

    strategy = alu_strategy(
        sorted_alu_ops=operations,
        acc_buffer_size=3,
        idx_to_store=[destination],
    )

    assert len(strategy) == 2
    assert all(step[3][0] == destination for step in strategy)
    assert destination in strategy[0][2]
    assert destination not in strategy[1][2]
    assert strategy[0][5] == []
    assert strategy[1][5] == [destination]

    values = {
        destination: -128,
        sources[0]: -127,
        sources[1]: -120,
        sources[2]: -125,
        sources[3]: -126,
    }
    assert _execute_strategy(strategy, values) == {destination: -120}


def test_destinations_are_stored_before_sram_slot_zero_is_reused() -> None:
    """Independent pooling outputs may safely reuse the same physical SRAM slot."""
    first_destination = (0, 0)
    second_destination = (0, 2)
    operations = [
        _max_operation(first_destination, (1, 0)),
        _max_operation(first_destination, (2, 0)),
        _max_operation(second_destination, (1, 2)),
        _max_operation(second_destination, (2, 2)),
    ]

    strategy = alu_strategy(
        sorted_alu_ops=operations,
        acc_buffer_size=3,
        idx_to_store=[first_destination, second_destination],
    )

    assert [step[5] for step in strategy] == [
        [first_destination],
        [second_destination],
    ]
    assert all(len(step[3]) <= 3 for step in strategy)

    values = {
        first_destination: -128,
        (1, 0): -121,
        (2, 0): -124,
        second_destination: -127,
        (1, 2): -126,
        (2, 2): -123,
    }
    assert _execute_strategy(strategy, values) == {
        first_destination: -121,
        second_destination: -123,
    }


if __name__ == "__main__":
    test_reduction_keeps_destination_in_a_stable_sram_slot()
    test_destinations_are_stored_before_sram_slot_zero_is_reused()
