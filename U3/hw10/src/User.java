import com.oocourse.spec2.main.UserInterface;
import com.oocourse.spec2.main.VideoInterface;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Collection;
import java.util.Set;

public class User implements UserInterface {

    private final int id;
    private final String name;
    private final int age;
    private int coins;

    private final Map<Integer, User> following = new HashMap<>();
    private final Map<Integer, User> followers = new HashMap<>();

    private final int[] followerAgeCounts = new int[4];

    private final IndexedList<Integer> receivedVideos = new IndexedList<>();
    private final Set<Integer> watchedVideos = new HashSet<>();
    private final Set<Integer> likedVideos = new HashSet<>();
    private final Set<Integer> medals = new HashSet<>();
    private final Map<Integer, Integer> contributions = new HashMap<>();

    public User(int id, String name, int age) {
        this.id = id;
        this.name = name;
        this.age = age;
    }

    @Override
    public int getId() {
        return id;
    }

    @Override
    public String getName() {
        return name;
    }

    @Override
    public int getAge() {
        return age;
    }

    @Override
    public boolean isFollowing(UserInterface user) {
        if (user == null) {
            return false;
        }
        return following.containsKey(user.getId());
    }

    @Override
    public boolean containsFollower(UserInterface user) {
        if (user == null) {
            return false;
        }
        return followers.containsKey(user.getId());
    }

    @Override
    public boolean hasReceivedVideo(VideoInterface video) {
        if (video == null) {
            return false;
        }
        return receivedVideos.contains(video.getId());
    }

    @Override
    public double[] queryAgeRatio() {
        double[] ans = new double[4];
        if (followers.isEmpty()) {
            return ans;
        }
        for (int i = 0; i < 4; i++) {
            ans[i] = 1.0 * followerAgeCounts[i] / followers.size();
        }
        return ans;
    }

    @Override
    public List<Integer> queryReceivedUnwatchedVideos() {
        return receivedVideos.getFirst(5);
    }

    @Override
    public boolean equals(Object obj) {
        if (!(obj instanceof UserInterface)) {
            return false;
        }
        return ((UserInterface) obj).getId() == id;
    }

    @Override
    public boolean hasWatchedVideo(VideoInterface video) {
        if (video == null) {
            return false;
        }
        return watchedVideos.contains(video.getId());
    }

    @Override
    public boolean hasLikedVideo(VideoInterface video) {
        if (video == null) {
            return false;
        }
        return likedVideos.contains(video.getId());
    }

    @Override
    public int getCoins() {
        return coins;
    }

    @Override
    public boolean hasMedal(int uploaderId) {
        return medals.contains(uploaderId);
    }

    public void addFollowing(User target) {
        following.put(target.getId(), target);
    }

    public void removeFollowing(User target) {
        following.remove(target.getId());
    }

    public void addFollower(User follower) {
        followers.put(follower.getId(), follower);
        int age = follower.getAge();
        if (age <= 16) {
            followerAgeCounts[0]++;
        } else if (age <= 30) {
            followerAgeCounts[1]++;
        } else if (age <= 45) {
            followerAgeCounts[2]++;
        } else {
            followerAgeCounts[3]++;
        }
    }

    public void removeFollower(UserInterface follower) {
        followers.remove(follower.getId());
        int age = follower.getAge();
        if (age <= 16) {
            followerAgeCounts[0]--;
        } else if (age <= 30) {
            followerAgeCounts[1]--;
        } else if (age <= 45) {
            followerAgeCounts[2]--;
        } else {
            followerAgeCounts[3]--;
        }
    }

    public void receiveVideo(int videoId) {
        receivedVideos.addToHead(videoId);
    }

    public void watchVideo(VideoInterface video) {
        watchedVideos.add(video.getId());
        int videoId = video.getId();
        receivedVideos.removeAll(videoId);
    }

    public void addCoins(int amount) {
        coins += amount;
    }

    public void likeVideo(VideoInterface video) {
        likedVideos.add(video.getId());
    }

    public void unlikeVideo(VideoInterface video) {
        likedVideos.remove(video.getId());
    }

    public void addMedal(int uploaderId) {
        medals.add(uploaderId);
    }

    public void addContribution(User contributor, int amount) {
        contributions.put(contributor.getId(),
            contributions.getOrDefault(contributor.getId(), 0) + amount);
    }

    public boolean hasContributors() {
        return !contributions.isEmpty();
    }

    public int queryBestContributor() {
        int bestId = 0;
        int bestValue = Integer.MIN_VALUE;
        for (Map.Entry<Integer, Integer> entry : contributions.entrySet()) {
            int contributorId = entry.getKey();
            int value = entry.getValue();
            if (value > bestValue || (value == bestValue && contributorId < bestId)) {
                bestValue = value;
                bestId = contributorId;
            }
        }
        return bestId;
    }

    public Collection<User> getFollowing() {
        return following.values();
    }

    public Collection<User> getFollowers() {
        return followers.values();
    }

    public boolean strictEquals(UserInterface other) {
        if (other == null) {
            return false;
        }
        return id == other.getId()
            && Objects.equals(name, other.getName())
            && age == other.getAge()
            && coins == other.getCoins();
    }
}
