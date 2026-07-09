import com.oocourse.spec2.exceptions.DuplicateMedalException;
import com.oocourse.spec2.exceptions.DuplicateSubscriptionException;
import com.oocourse.spec2.exceptions.EqualCommentIdException;
import com.oocourse.spec2.exceptions.EqualUserIdException;
import com.oocourse.spec2.exceptions.EqualVideoIdException;
import com.oocourse.spec2.exceptions.FollowLinkNotFoundException;
import com.oocourse.spec2.exceptions.InsufficientCoinsException;
import com.oocourse.spec2.exceptions.InvalidAgeException;
import com.oocourse.spec2.exceptions.InvalidCoinsException;
import com.oocourse.spec2.exceptions.InvalidCommentException;
import com.oocourse.spec2.exceptions.InvalidTypeException;
import com.oocourse.spec2.exceptions.NoContributorsException;
import com.oocourse.spec2.exceptions.SelfSubscriptionException;
import com.oocourse.spec2.exceptions.UncessException;
import com.oocourse.spec2.exceptions.UserIdNotFoundException;
import com.oocourse.spec2.exceptions.VideoIdNotFoundException;
import com.oocourse.spec2.exceptions.VideoUnwatchedException;
import com.oocourse.spec2.main.NetworkInterface;
import com.oocourse.spec2.main.UserInterface;
import com.oocourse.spec2.main.VideoInterface;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class Network implements NetworkInterface {

    private final Map<Integer, User> userMap = new HashMap<>();
    private final Map<Integer, Video> videoMap = new HashMap<>();
    private final Map<String, Video> mostPopularCache = new HashMap<>();
    private final Set<String> mostPopularDirtyTypes = new HashSet<>();

    private int mutualFollowingSum = 0;
    private boolean longestDirty = true;
    private int longestDecSeqCache = 0;

    public Network() {
    }

    @Override
    public boolean containsUser(int id) {
        return userMap.containsKey(id);
    }

    @Override
    public UserInterface getUser(int id) {
        return userMap.get(id);
    }

    @Override
    public boolean containsVideo(int id) {
        return videoMap.containsKey(id);
    }

    @Override
    public VideoInterface getVideo(int id) {
        return videoMap.get(id);
    }

    @Override
    public void addUser(int id, String name, int age)
        throws EqualUserIdException, InvalidAgeException {
        if (containsUser(id)) {
            throw new EqualUserIdException(id);
        }
        if (age < 0 || age > 110) {
            throw new InvalidAgeException(age);
        }
        userMap.put(id, new User(id, name, age));
        longestDirty = true;
        System.out.println("add_user succeeded");
    }

    @Override
    public void uploadVideo(int uploaderId, int videoId, String type)
        throws UserIdNotFoundException, EqualVideoIdException, InvalidTypeException {
        User uploader = userMap.get(uploaderId);
        if (uploader == null) {
            throw new UserIdNotFoundException(uploaderId);
        }
        if (containsVideo(videoId)) {
            throw new EqualVideoIdException(videoId);
        }
        if (!isValidType(type)) {
            throw new InvalidTypeException(type);
        }
        Video video = new Video(videoId, uploaderId, type);
        videoMap.put(videoId, video);
        markMostPopularDirty(type);
        for (User follower : uploader.getFollowers()) {
            follower.receiveVideo(videoId);
        }
        System.out.println("upload_video succeeded");
    }

    @Override
    public boolean isValidType(String type) {
        return "tech".equals(type) || "music".equals(type) || "sport".equals(type)
            || "game".equals(type) || "food".equals(type) || "travel".equals(type)
            || "comedy".equals(type);
    }

    @Override
    public void followUser(int id1, int id2)
        throws UserIdNotFoundException, SelfSubscriptionException,
        DuplicateSubscriptionException {
        User user1 = userMap.get(id1);
        if (user1 == null) {
            throw new UserIdNotFoundException(id1);
        }
        User user2 = userMap.get(id2);
        if (user2 == null) {
            throw new UserIdNotFoundException(id2);
        }
        if (id1 == id2) {
            throw new SelfSubscriptionException(id1);
        }
        if (user1.isFollowing(user2)) {
            throw new DuplicateSubscriptionException(id1, id2);
        }
        user1.addFollowing(user2);
        user2.addFollower(user1);
        if (user2.isFollowing(user1)) {
            mutualFollowingSum++;
        }
        longestDirty = true;
        System.out.println("follow_user succeeded");
    }

    @Override
    public void unfollowUser(int id1, int id2)
        throws UserIdNotFoundException, FollowLinkNotFoundException {
        User user1 = userMap.get(id1);
        if (user1 == null) {
            throw new UserIdNotFoundException(id1);
        }
        User user2 = userMap.get(id2);
        if (user2 == null) {
            throw new UserIdNotFoundException(id2);
        }
        if (!user1.isFollowing(user2)) {
            throw new FollowLinkNotFoundException(id1, id2);
        }
        if (user2.isFollowing(user1)) {
            mutualFollowingSum--;
        }
        user1.removeFollowing(user2);
        user2.removeFollower(user1);
        longestDirty = true;
        System.out.println("unfollow_user succeeded");
    }

    @Override
    public void watchVideo(int userId, int videoId)
        throws UserIdNotFoundException, VideoIdNotFoundException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        user.watchVideo(video);
        video.addPlayCount();
        markMostPopularDirty(video.getType());
        System.out.println("watch_video succeeded");
    }

    @Override
    public List<Integer> queryReceivedUnwatchedVideos(int userId)
        throws UserIdNotFoundException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        return user.queryReceivedUnwatchedVideos();
    }

    @Override
    public double[] queryUpFollowersAgeRatio(int upId)
        throws UserIdNotFoundException {
        User up = userMap.get(upId);
        if (up == null) {
            throw new UserIdNotFoundException(upId);
        }
        return up.queryAgeRatio();
    }

    @Override
    public int queryMutualFollowingSum() {
        return mutualFollowingSum;
    }

    @Override
    public int queryShortestPath(int id1, int id2)
        throws UserIdNotFoundException, UncessException {
        if (!userMap.containsKey(id1)) {
            throw new UserIdNotFoundException(id1);
        }
        if (!userMap.containsKey(id2)) {
            throw new UserIdNotFoundException(id2);
        }
        return GraphHelper.bfsShortestPath(userMap, id1, id2);
    }

    @Override
    public void addUserCoins(int userId, int coins) throws UserIdNotFoundException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        user.addCoins(coins);
        System.out.println("add_user_coins succeeded");
    }

    @Override
    public void likeVideo(int userId, int videoId)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        VideoUnwatchedException, EqualUserIdException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        if (userId == video.getUploaderId()) {
            throw new EqualUserIdException(userId);
        }
        if (!user.hasWatchedVideo(video)) {
            throw new VideoUnwatchedException(userId, videoId);
        }
        if (user.hasLikedVideo(video)) {
            user.unlikeVideo(video);
            video.removeLike();
            markMostPopularDirty(video.getType());
            System.out.println("unlike_video succeeded");
        } else {
            user.likeVideo(video);
            video.addLike();
            markMostPopularDirty(video.getType());
            System.out.println("like_video succeeded");
        }
    }

    @Override
    public void coinVideo(int userId, int videoId, int amount)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        InsufficientCoinsException, VideoUnwatchedException,
        InvalidCoinsException, EqualUserIdException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        if (userId == video.getUploaderId()) {
            throw new EqualUserIdException(userId);
        }
        if (!user.hasWatchedVideo(video)) {
            throw new VideoUnwatchedException(userId, videoId);
        }
        if (amount != 1 && amount != 2) {
            throw new InvalidCoinsException(amount);
        }
        if (user.getCoins() < amount) {
            throw new InsufficientCoinsException(userId);
        }
        User uploader = userMap.get(video.getUploaderId());
        user.addCoins(-amount);
        uploader.addCoins(amount);
        uploader.addContribution(user, amount);
        video.addCoins(amount);
        markMostPopularDirty(video.getType());
        System.out.println("coin_video succeeded");
    }

    @Override
    public int queryBestContributor(int id)
        throws UserIdNotFoundException, NoContributorsException {
        User user = userMap.get(id);
        if (user == null) {
            throw new UserIdNotFoundException(id);
        }
        if (!user.hasContributors()) {
            throw new NoContributorsException(id);
        }
        return user.queryBestContributor();
    }

    @Override
    public void forwardVideo(int userId, int videoId, int followerId)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        FollowLinkNotFoundException, VideoUnwatchedException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        User follower = userMap.get(followerId);
        if (follower == null) {
            throw new UserIdNotFoundException(followerId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        if (!user.hasWatchedVideo(video)) {
            throw new VideoUnwatchedException(userId, videoId);
        }
        if (!user.containsFollower(follower)) {
            throw new FollowLinkNotFoundException(userId, followerId);
        }
        follower.receiveVideo(videoId);
        video.addForwardCount();
        markMostPopularDirty(video.getType());
        System.out.println("forward_video succeeded");
    }

    @Override
    public void sendComment(int userId, int videoId, int commentId, String comment)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        EqualCommentIdException, InvalidCommentException {
        if (!containsUser(userId)) {
            throw new UserIdNotFoundException(userId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        if (video.containsComment(commentId)) {
            throw new EqualCommentIdException(commentId);
        }
        if (comment == null || comment.isEmpty()) {
            throw new InvalidCommentException();
        }
        video.addComment(commentId, comment);
        System.out.println("send_comment succeeded");
    }

    @Override
    public int[] cleanSpamComments(int videoId, String keyword)
        throws VideoIdNotFoundException {
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        return video.cleanSpamComments(keyword);
    }

    @Override
    public VideoInterface queryMostPopularVideo(String type)
        throws InvalidTypeException {
        if (!isValidType(type)) {
            throw new InvalidTypeException(type);
        }
        if (!mostPopularCache.containsKey(type) || mostPopularDirtyTypes.contains(type)) {
            mostPopularCache.put(type, findMostPopularVideo(type));
            mostPopularDirtyTypes.remove(type);
        }
        return mostPopularCache.get(type);
    }

    private void markMostPopularDirty(String type) {
        mostPopularDirtyTypes.add(type);
    }

    private Video findMostPopularVideo(String type) {
        Video best = null;
        for (Video video : videoMap.values()) {
            if (!video.getType().equals(type)) {
                continue;
            }
            if (best == null || video.getHeat() > best.getHeat()
                || (video.getHeat() == best.getHeat() && video.getId() < best.getId())) {
                best = video;
            }
        }
        return best;
    }

    @Override
    public void purchaseMedal(int userId, int videoId, int amount)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        EqualUserIdException, InsufficientCoinsException, DuplicateMedalException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        int uploaderId = video.getUploaderId();
        if (userId == uploaderId) {
            throw new EqualUserIdException(userId);
        }
        if (user.getCoins() < amount) {
            throw new InsufficientCoinsException(userId);
        }
        if (user.hasMedal(uploaderId)) {
            throw new DuplicateMedalException(userId, uploaderId);
        }
        User uploader = userMap.get(uploaderId);
        user.addCoins(-amount);
        uploader.addCoins(amount);
        user.addMedal(uploaderId);
        System.out.println("purchase_medal succeeded");
    }

    @Override
    public int queryLongestDecSeq() {
        if (!longestDirty) {
            return longestDecSeqCache;
        }
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
        longestDecSeqCache = ans;
        longestDirty = false;
        return ans;
    }

    public UserInterface[] getUsers() {
        return userMap.values().toArray(new UserInterface[0]);
    }
}
