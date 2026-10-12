"""Relative-image proximity relationships and connected aircraft groups."""
import math


def get_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1+x2)/2, (y1+y2)/2)


def compute_distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])


def analyze_clustering(detections, distance_threshold=450):
    centers = [get_center(d["bbox"]) for d in detections]
    return [(i, j) for i in range(len(centers)) for j in range(i+1, len(centers))
            if compute_distance(centers[i], centers[j]) < distance_threshold]


def analyze_spatial(detections, width, height, distance_fraction=0.08):
    aircraft = [d for d in detections if d["class"] == "aircraft"]
    threshold = math.hypot(width, height)*distance_fraction
    pairs = analyze_clustering(aircraft, threshold)
    neighbors = {i: set() for i in range(len(aircraft))}
    for i, j in pairs:
        neighbors[i].add(j)
        neighbors[j].add(i)
    groups, visited = [], set()
    for i in neighbors:
        if i in visited or not neighbors[i]:
            continue
        component, pending = [], [i]
        while pending:
            node = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            pending.extend(neighbors[node]-visited)
        groups.append(sorted(component))
    possible = len(aircraft)*(len(aircraft)-1)/2
    return {"pairs": pairs, "groups": groups, "group_count": len(groups),
            "isolated_indices": [i for i in neighbors if not neighbors[i]],
            "isolated_count": sum(not value for value in neighbors.values()),
            "pair_density": len(pairs)/possible if possible else 0.0,
            "distance_threshold_pixels": round(threshold, 2), "distance_fraction": distance_fraction}
