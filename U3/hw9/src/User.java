import com.oocourse.spec1.main.UserInterface;
import com.oocourse.spec1.main.VideoInterface;

import java.util.HashMap;
import java.util.Map;
import java.util.List;
import java.util.Objects;
import java.util.Collection;

public class User implements UserInterface {

    private final int id;
    private final String name;
    private final int age;

    private final Map<Integer, User> following = new HashMap<>();
    private final Map<Integer, User> followers = new HashMap<>();

    private final int[] followerAgeCounts = new int[4];

    private final IndexedList<Integer> receivedVideos = new IndexedList<>();

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

    public void watchVideo(int videoId) {
        receivedVideos.removeAll(videoId);
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
            && age == other.getAge();
    }
}
