"""Partition VTA ALU operations while preserving accumulator SRAM locations."""

from typing import Any, Dict, List, Sequence, Tuple

from matrix_partitioning.utils_strategies import get_dst_src_vectors


# TODO: Move these shared partitioning types to a dedicated strategy_types
# module. Replace the positional seven-list tuple with a StrategyStep NamedTuple
# used consistently by all partitioning strategies and instruction generation.
AluOperation = List[Any]
VectorIndex = Tuple[int, int]
StrategyStep = Tuple[
    List[Any],
    List[Any],
    List[VectorIndex],
    List[VectorIndex],
    List[VectorIndex],
    List[VectorIndex],
    List[AluOperation],
]


def _unique_vectors(vectors: Sequence[VectorIndex]) -> List[VectorIndex]:
    """Returns vectors in first-seen order without duplicates.

    Args:
        vectors: SRAM vector identifiers to deduplicate.

    Returns:
        Ordered list containing each vector identifier once.
    """
    return list(dict.fromkeys(vectors))


def _split_vector_operation(
    operation: AluOperation,
    source_capacity: int,
) -> List[Tuple[AluOperation, List[VectorIndex]]]:
    """Splits one ALU operation into source sets that fit beside its destination.

    Operation order and repeated sources are preserved because repetitions are
    significant for operations such as ADD. Only the SRAM load list is
    deduplicated.

    Args:
        operation: Lowered ALU operation containing exactly one destination.
        source_capacity: Maximum number of distinct source vectors in one step.

    Returns:
        Operation fragments paired with the distinct sources they require.

    Raises:
        ValueError: If no source slot is available for a vector-vector operation.
    """
    destination, sources = get_dst_src_vectors(operation)
    if not sources:
        return [(operation, [])]
    if source_capacity < 1:
        raise ValueError("An ALU vector-vector operation requires one source slot")

    fragments: List[Tuple[AluOperation, List[VectorIndex]]] = []
    current_sources: List[VectorIndex] = []
    current_unique_sources: List[VectorIndex] = []

    for source in sources:
        candidate_unique = _unique_vectors(current_unique_sources + [source])

        # Close the current fragment before an additional distinct source would
        # exceed the SRAM slots available beside the live destination vector.
        if current_sources and len(candidate_unique) > source_capacity:
            fragment = [operation[0], operation[1], [(destination, current_sources)]]
            fragments.append((fragment, current_unique_sources))
            current_sources = []
            current_unique_sources = []

        current_sources.append(source)
        current_unique_sources = _unique_vectors(current_unique_sources + [source])

    fragment = [operation[0], operation[1], [(destination, current_sources)]]
    fragments.append((fragment, current_unique_sources))
    return fragments


def _group_operations_by_destination(
    sorted_alu_ops: Sequence[AluOperation],
) -> List[Tuple[VectorIndex, List[AluOperation]]]:
    """Groups consecutive, pre-sorted ALU operations by destination vector.

    Args:
        sorted_alu_ops: Operations sorted stably by destination vector.

    Returns:
        Destination vectors paired with their ordered operations.
    """
    grouped: List[Tuple[VectorIndex, List[AluOperation]]] = []
    operations_by_destination: Dict[VectorIndex, List[AluOperation]] = {}

    for operation in sorted_alu_ops:
        destination, _ = get_dst_src_vectors(operation)
        if destination not in operations_by_destination:
            operations_by_destination[destination] = []

            # Preserve first-seen destination order so strategy generation and
            # the resulting dense DRAM store order remain deterministic.
            grouped.append((destination, operations_by_destination[destination]))
        operations_by_destination[destination].append(operation)

    return grouped


def alu_strategy(
    sorted_alu_ops: Sequence[AluOperation],
    acc_buffer_size: int,
    idx_to_store: Sequence[VectorIndex],
) -> List[StrategyStep]:
    """Builds an ALU partition strategy with stable SRAM destination addresses.

    A reduction such as MaxPool updates one destination several times. When the
    reduction spans multiple strategy steps, that destination must retain the
    same SRAM address until its final store. Each destination is therefore kept
    at slot zero, while source vectors occupy the remaining slots and may be
    replaced between steps.

    Args:
        sorted_alu_ops: Lowered ALU operations, stably sorted by destination.
        acc_buffer_size: Number of accumulator vectors available in SRAM.
        idx_to_store: Ordered output vectors used to derive dense DRAM addresses.

    Returns:
        Strategy steps in ``(A, B, X, SRAM, DRAM, C, operations)`` form.

    Raises:
        ValueError: If the accumulator cannot hold a destination and a source.
    """
    if acc_buffer_size < 2:
        raise ValueError(
            "The accumulator buffer must hold at least one destination and one source"
        )

    strategy: List[StrategyStep] = []
    dram_status = list(idx_to_store)
    source_capacity = acc_buffer_size - 1

    for destination, destination_operations in _group_operations_by_destination(
        sorted_alu_ops
    ):
        segments: List[Tuple[List[AluOperation], List[VectorIndex]]] = []
        segment_operations: List[AluOperation] = []
        segment_sources: List[VectorIndex] = []

        for operation in destination_operations:
            for fragment, fragment_sources in _split_vector_operation(
                operation, source_capacity
            ):
                combined_sources = _unique_vectors(segment_sources + fragment_sources)

                # Operations sharing a destination can execute in one segment
                # only while all their distinct sources fit in ACC SRAM.
                if segment_operations and len(combined_sources) > source_capacity:
                    segments.append((segment_operations, segment_sources))
                    segment_operations = []
                    segment_sources = []

                segment_operations.append(fragment)
                segment_sources = _unique_vectors(segment_sources + fragment_sources)

        if segment_operations:
            segments.append((segment_operations, segment_sources))

        for segment_index, (operations, sources) in enumerate(segments):
            # Reserve SRAM slot zero for the destination throughout the complete
            # reduction; replace only the source slots between partial segments.
            sram_status = [destination] + [
                source for source in sources if source != destination
            ]

            # Load the destination once. Later segments reuse its partial result
            # already held in slot zero and load only their new source vectors.
            load_acc = list(sram_status) if segment_index == 0 else sram_status[1:]
            is_final_segment = segment_index == len(segments) - 1

            # Expose the destination to STORE only after every source fragment
            # contributing to the reduction has executed.
            store_acc = [destination] if is_final_segment else []

            strategy.append(
                ([], [], load_acc, sram_status, dram_status, store_acc, operations)
            )

    return strategy
