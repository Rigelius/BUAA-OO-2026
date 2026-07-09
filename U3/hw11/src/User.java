import com.oocourse.spec3.main.UserInterface;
import com.oocourse.spec3.main.VideoInterface;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class User implements UserInterface {

    private static final String[] TYPES = {
        "tech", "music", "sport", "game", "food", "travel", "comedy"
    };

    private final int id;
    private final String name;
    private final int age;
    private final Map<Integer, User> following = new HashMap<>();
    private final Map<Integer, User> followers = new HashMap<>();
    private final int[] followerAgeCounts = new int[4];
    private final IndexedList<Integer> receivedVideos = new IndexedList<>();
    private final Set<Integer> watchedVideoIds = new HashSet<>();
    private final List<VideoInterface> watchedVideoList = new ArrayList<>();
    private final List<VideoInterface> likedVideoList = new ArrayList<>();
    private final Set<Integer> likedVideoIds = new HashSet<>();
    private final Set<Integer> medals = new HashSet<>();
    private final Map<Integer, Integer> contributions = new HashMap<>();
    private final int[] typeCounts = new int[7];
    private final Map<Integer, Video> videos = new HashMap<>();
    private final int[] influences = new int[7];
    private int coins;
    private int bestContributorId = Integer.MAX_VALUE;
    private int bestContributorValue = -1;

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
        return watchedVideoIds.contains(video.getId());
    }

    @Override
    public boolean hasLikedVideo(VideoInterface video) {
        if (video == null) {
            return false;
        }
        return likedVideoIds.contains(video.getId());
    }

    @Override
    public int getCoins() {
        return coins;
    }

    @Override
    public boolean hasMedal(int uploaderId) {
        return medals.contains(uploaderId);
    }

    @Override
    public int getInterest(String type, int totalVideos) {
        int idx = getTypeIndex(type);
        return typeCounts[idx] * (totalVideos - watchedVideoIds.size() + 1);
    }

    @Override
    public int getInfluence(String type) {
        int idx = getTypeIndex(type);
        if (idx < 0) {
            return 0;
        }
        return influences[idx];
    }

    public void updateInfluence(String type, int delta) {
        int idx = getTypeIndex(type);
        if (idx >= 0) {
            influences[idx] += delta;
        }
    }

    @Override
    public List<Integer> getProfile(int totalVideos) {
        List<Integer> ans = new ArrayList<>();
        for (String type : TYPES) {
            ans.add(getInterest(type, totalVideos));
        }
        return ans;
    }

    @Override
    public long computeUpScore(UserInterface up, int totalVideos) {
        long ans = 0;
        for (String type : TYPES) {
            ans += (long) getInterest(type, totalVideos) * up.getInfluence(type);
        }
        return ans;
    }

    private int getTypeIndex(String type) {
        for (int i = 0; i < TYPES.length; i++) {
            if (TYPES[i].equals(type)) {
                return i;
            }
        }
        return -1;
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
        int videoId = video.getId();
        if (!watchedVideoIds.contains(videoId)) {
            watchedVideoIds.add(videoId);
            watchedVideoList.add(video);
        }
        receivedVideos.removeAll(videoId);
        int idx = getTypeIndex(video.getType());
        if (idx >= 0) {
            typeCounts[idx]++;
        }
    }

    public void addCoins(int amount) {
        coins += amount;
    }

    public void likeVideo(VideoInterface video) {
        if (!likedVideoIds.contains(video.getId())) {
            likedVideoIds.add(video.getId());
            likedVideoList.add(video);
        }
    }

    public void unlikeVideo(VideoInterface video) {
        if (likedVideoIds.remove(video.getId())) {
            likedVideoList.removeIf(v -> v.getId() == video.getId());
        }
    }

    public void addMedal(int uploaderId) {
        medals.add(uploaderId);
    }

    public void addContribution(User contributor, int amount) {
        int id = contributor.getId();
        int newValue = contributions.getOrDefault(id, 0) + amount;
        contributions.put(id, newValue);

        if (newValue > bestContributorValue
            || (newValue == bestContributorValue && id < bestContributorId)) {
            bestContributorValue = newValue;
            bestContributorId = id;
        }
    }

    public boolean hasContributors() {
        return !contributions.isEmpty();
    }

    public int queryBestContributor() {
        return bestContributorId;
    }

    public Collection<User> getFollowing() {
        return following.values();
    }

    public Collection<User> getFollowers() {
        return followers.values();
    }

    public void addVideo(Video video) {
        videos.put(video.getId(), video);
        updateInfluence(video.getType(), video.getHeat());
    }

    public List<Integer> getWatchedVideoIds() {
        return new ArrayList<>(watchedVideoIds);
    }

    public int[] getTypeCounts() {
        return typeCounts;
    }

    public boolean strictEquals(UserInterface other) {
        if (!(other instanceof User)) {
            return false;
        }
        User otherUser = (User) other;
        if (id != other.getId() || age != other.getAge() || coins != other.getCoins()) {
            return false;
        }
        if (!Objects.equals(name, other.getName())) {
            return false;
        }
        if (!following.equals(otherUser.following) || !followers.equals(otherUser.followers)) {
            return false;
        }
        if (!Arrays.equals(followerAgeCounts, otherUser.followerAgeCounts)) {
            return false;
        }
        if (!receivedVideos.toList().equals(otherUser.receivedVideos.toList())) {
            return false;
        }
        if (!watchedVideoIds.equals(otherUser.watchedVideoIds)) {
            return false;
        }
        if (!watchedVideoList.equals(otherUser.watchedVideoList)) {
            return false;
        }
        if (!likedVideoIds.equals(otherUser.likedVideoIds)) {
            return false;
        }
        if (!likedVideoList.equals(otherUser.likedVideoList)) {
            return false;
        }
        if (!medals.equals(otherUser.medals) || !contributions.equals(otherUser.contributions)) {
            return false;
        }
        if (!Arrays.equals(typeCounts, otherUser.typeCounts) || !videos.equals(otherUser.videos)) {
            return false;
        }
        if (!Arrays.equals(influences, otherUser.influences)) {
            return false;
        }
        return bestContributorId == otherUser.bestContributorId
            && bestContributorValue == otherUser.bestContributorValue;
    }
}
