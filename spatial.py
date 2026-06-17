import math


def get_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def compute_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) #Euclidean distance


def analyze_clustering(detections, distance_threshold=450):
    clusters = []

    centers = [get_center(d["bbox"]) for d in detections]

    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            dist = compute_distance(centers[i], centers[j])
            if dist < distance_threshold:
                clusters.append((i, j))

    return clusters