def encode_motor_cmd(w):
    return 'M,%.3f,%.3f,%.3f,%.3f' % (w[0], w[1], w[2], w[3])


def encode_enable(enabled):
    return 'S,%d' % (1 if enabled else 0)


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    parts = line.split(',')
    if parts[0] == 'T' and len(parts) == 4:
        try:
            vals = [int(v) for v in parts[1:]]
        except ValueError:
            return None
        return {'type': 'T', 'estop': vals[0] == 1,
                'bumper_front': vals[1] == 1, 'bumper_rear': vals[2] == 1}
    if parts[0] == 'H' and len(parts) == 2:
        try:
            return {'type': 'H', 'millis': int(parts[1])}
        except ValueError:
            return None
    return None
