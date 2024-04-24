import os

CAPTURE_DIR = "captures"


def get_overlap(segment, all_segments):
    '''
    for a given segment, find all segments which have overlapping bounds
    e.g. (0, 5) overlaps with (1,2) and (4,6)
    '''
    s,e = segment
    idx = 0
    overlaps = []
    next_s, next_e, _= all_segments[idx]
    while (s >= next_e) and (idx < len(all_segments)-1):
        idx += 1
        next_s, next_e, _= all_segments[idx]

    while (next_s < e) and (idx < len(all_segments)-1):
        overlaps.append(all_segments[idx])
        if idx >= len(all_segments)-1:
            break
        else:
            idx += 1
            next_s, next_e, _= all_segments[idx]
    return overlaps


def get_capture_fname(video_fname):
    files = os.listdir(CAPTURE_DIR)
    i = 0
    num = f"{i:03}"
    candidate_fname = f"{video_fname.replace('.mp4','')}_caps_{num}.json"
    while candidate_fname in files:
        i += 1
        num = f"{i:03}"
        candidate_fname = f"{video_fname.replace('.mp4','')}_caps_{num}.json"
    return  f"{CAPTURE_DIR}/{candidate_fname}"


if __name__ == "__main__":
    vid_fname = "test.mp4"
    fname1 = get_capture_fname(vid_fname)
    print(fname1)
    os.system(f'touch {fname1}')
    fname2 = get_capture_fname(vid_fname)
    print(fname2)
    os.system(f'rm {fname1}')
