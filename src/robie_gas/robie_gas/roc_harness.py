import subprocess, time, os, itertools

THRESHOLDS = [50, 100, 150, 200, 250, 300]
NOISE_LEVELS = [0, 2, 4, 8, 16]
REPEATS = 3
TIMEOUT = 100

def run_single(threshold, noise_sigma, leak_present, run_id):
    log_dir = os.path.expanduser('~/robie_ws/logs/roc')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'run_%d.csv' % run_id)

    plume_cmd = ['ros2', 'run', 'robie_gas', 'plume_sim', '--ros-args',
                 '-p', 'peak:=%f' % (400.0 if leak_present else 0.0),
                 '-p', 'noise_sigma:=%f' % noise_sigma]

    climber_cmd = ['ros2', 'run', 'robie_gas', 'gas_climber', '--ros-args',
                   '-p', 'threshold:=%f' % threshold,
                   '-p', 'log_file:=%s' % log_file,
                   '-p', 'auto_shutdown:=true',
                   '-p', 'max_run_s:=40.0',
                   '-p', 'timeout_s:=90.0']

    plume_proc = subprocess.Popen(plume_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    climber_proc = subprocess.Popen(climber_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        climber_proc.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        climber_proc.kill()
        plume_proc.kill()
        return 'TIMEOUT'

    plume_proc.kill()
    time.sleep(0.3)
    return 'DONE'

def main():
    run_id = 0
    total = len(THRESHOLDS) * len(NOISE_LEVELS) * 2 * REPEATS
    print('Starting corrected ROC batch: %d runs' % total)
    for threshold, noise in itertools.product(THRESHOLDS, NOISE_LEVELS):
        for leak_present in [True, False]:
            for _ in range(REPEATS):
                run_id += 1
                outcome = run_single(threshold, noise, leak_present, run_id)
                print('[%d/%d] thresh=%d noise=%d leak=%s -> %s'
                      % (run_id, total, threshold, noise, leak_present, outcome))
    print('Batch complete. Now run: python3 ~/robie_ws/parse_roc.py')

if __name__ == '__main__':
    main()
