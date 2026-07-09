import com.oocourse.spec2.exceptions.UncessException;

import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;

public final class GraphHelper {

    private GraphHelper() {}

    public static int bfsShortestPath(
        Map<Integer, User> userMap,
        int sourceId,
        int targetId) throws UncessException {
        if (sourceId == targetId) {
            return 0;
        }
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        HashMap<Integer, Integer> dist = new HashMap<>();
        dist.put(sourceId, 0);
        queue.add(sourceId);
        while (!queue.isEmpty()) {
            int id = queue.poll();
            int d = dist.get(id);
            for (User u : userMap.get(id).getFollowing()) {
                int uid = u.getId();
                if (!dist.containsKey(uid)) {
                    if (uid == targetId) {
                        return d + 1;
                    }
                    dist.put(uid, d + 1);
                    queue.add(uid);
                }
            }
        }
        throw new UncessException(sourceId, targetId);
    }
}
