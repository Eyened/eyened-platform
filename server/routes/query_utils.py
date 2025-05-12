from collections import defaultdict

sqlalchemy_operators = {
    "eq": lambda column, value: column == value,
    "ne": lambda column, value: column != value,
    "gt": lambda column, value: column > value,
    "lt": lambda column, value: column < value,
    "gte": lambda column, value: column >= value,
    "lte": lambda column, value: column <= value,
    "in": lambda column, value: column.in_(value if isinstance(value, list) else [value]),
    "not_in": lambda column, value: ~column.in_(value if isinstance(value, list) else [value]),
    "like": lambda column, value: column.like(f"%{value}%"),
    "ilike": lambda column, value: column.ilike(f"%{value}%"),
    "startswith": lambda column, value: column.startswith(value),
    "endswith": lambda column, value: column.endswith(value),
    "is_null": lambda column, value: column.is_(None) if value else column.isnot(None)
}


def decode_params(params_multi_items):
    """
    Decode query parameters into a structured format with operators.

    Args:
        params_multi_items: List of (key, value) tuples from query parameters
        keys are split by '~~' to separate field names from operators.

    Returns:
        Dict mapping field names to (operator, value) tuples
    """
    # Group values by parameter name
    param_dict = defaultdict(list)
    for key, value in params_multi_items:
        param_dict[key].append(value)

    result = {}
    for key, values in param_dict.items():
        # Parse field name and operator
        key_parts = key.split("~~")
        field = key_parts[0]

        if len(key_parts) > 1:
            operator = key_parts[1]
            if operator not in ("not_in", "in"):
                value = values[0]
        else:
            # default operator
            if len(values) == 1:
                operator = "eq"
                value = values[0]
            else:
                operator = "in"
                value = values

        result[field, operator] = value

    return result


def apply_filters(query, column_mapping, params):
    applied = False

    for field, (operator, value) in params.items():
        if field not in column_mapping:
            continue
        print("applying filter", field, operator, value)
        applied = True

        column = column_mapping[field]
        op_func = sqlalchemy_operators[operator]

        query = query.where(op_func(column, value))

    return query, applied
