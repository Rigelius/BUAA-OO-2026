import com.oocourse.spec3.exceptions.UncessException;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class NetworkHelper {

    public static class UpScore {
        private int id;
        private long score;

        public UpScore(int id, long score) {
            this.id = id;
            this.score = score;
        }

        public int getId() {
            return id;
        }

        public long getScore() {
            return score;
        }
    }

    public static int compare(UpScore a, UpScore b) {
        if (a.getScore() != b.getScore()) {
            return Long.compare(b.getScore(), a.getScore());
        }
        return Integer.compare(a.getId(), b.getId());
    }

    public static int fastSelect(List<UpScore> list, int l, int r, int k) {
        if (l == r) {
            return list.get(l).getId();
        }
        int i = l - 1;
        int j = r + 1;
        UpScore x = list.get(l + (r - l) / 2);

        while (i < j) {
            do {
                i++;
            } while (compare(list.get(i), x) < 0);
            do {
                j--;
            } while (compare(list.get(j), x) > 0);
            if (i < j) {
                swap(list, i, j);
            }
        }

        int leftLength = j - l + 1;
        if (leftLength >= k) {
            return fastSelect(list, l, j, k);
        } else {
            return fastSelect(list, j + 1, r, k - leftLength);
        }
    }

    private static void swap(List<UpScore> list, int i, int j) {
        UpScore temp = list.get(i);
        list.set(i, list.get(j));
        list.set(j, temp);
    }

    public static int bfsShortestPath(Map<Integer, User> userMap, int id1, int id2)
        throws UncessException {
        if (id1 == id2) {
            return 0;
        }
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        HashMap<Integer, Integer> dist = new HashMap<>();
        dist.put(id1, 0);
        queue.add(id1);
        while (!queue.isEmpty()) {
            int id = queue.poll();
            int d = dist.get(id);
            for (User u : userMap.get(id).getFollowing()) {
                int uid = u.getId();
                if (!dist.containsKey(uid)) {
                    if (uid == id2) {
                        return d + 1;
                    }
                    dist.put(uid, d + 1);
                    queue.add(uid);
                }
            }
        }
        throw new UncessException(id1, id2);
    }

    public static int calculateLongestDecSeq(Map<Integer, User> userMap) {
        List<User> users = new ArrayList<>(userMap.values());
        users.sort(Comparator.comparingInt(User::getAge));
        Map<Integer, Integer> dp = new HashMap<>();
        int ans = 0;
        for (User user : users) {
            int best = 1;
            for (User next : user.getFollowing()) {
                if (user.getAge() > next.getAge()) {
                    best = Math.max(best, dp.get(next.getId()) + 1);
                }
            }
            dp.put(user.getId(), best);
            ans = Math.max(ans, best);
        }
        return ans;
    }

    public static int[] queryGlobalBestContributor(Map<Integer, User> userMap) {
        Map<Integer, Integer> counts = new HashMap<>();
        for (User user : userMap.values()) {
            if (user.hasContributors()) {
                int bestId = user.queryBestContributor();
                counts.put(bestId, counts.getOrDefault(bestId, 0) + 1);
            }
        }
        if (counts.isEmpty()) {
            return new int[]{0, 0};
        }
        int bestId = Integer.MAX_VALUE;
        int maxCount = -1;
        for (Map.Entry<Integer, Integer> entry : counts.entrySet()) {
            int id = entry.getKey();
            int count = entry.getValue();
            if (count > maxCount || (count == maxCount && id < bestId)) {
                maxCount = count;
                bestId = id;
            }
        }
        return new int[]{bestId, maxCount};
    }

    public static int queryMostInfluentialUp(Map<Integer, User> userMap, String type) {
        int bestId = Integer.MAX_VALUE;
        long maxInfluence = -1;
        for (User up : userMap.values()) {
            int influence = up.getInfluence(type);
            if (influence > maxInfluence || (influence == maxInfluence && up.getId() < bestId)) {
                maxInfluence = influence;
                bestId = up.getId();
            }
        }
        return bestId;
    }
}
