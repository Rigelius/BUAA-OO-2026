import com.oocourse.spec3.exceptions.ColdStartUserException;
import com.oocourse.spec3.exceptions.ColdStartVideoException;
import com.oocourse.spec3.exceptions.DuplicateMedalException;
import com.oocourse.spec3.exceptions.DuplicateSubscriptionException;
import com.oocourse.spec3.exceptions.EqualCommentIdException;
import com.oocourse.spec3.exceptions.EqualUserIdException;
import com.oocourse.spec3.exceptions.EqualVideoIdException;
import com.oocourse.spec3.exceptions.FollowLinkNotFoundException;
import com.oocourse.spec3.exceptions.InsufficientCoinsException;
import com.oocourse.spec3.exceptions.InvalidAgeException;
import com.oocourse.spec3.exceptions.InvalidCoinsException;
import com.oocourse.spec3.exceptions.InvalidCommentException;
import com.oocourse.spec3.exceptions.InvalidRankException;
import com.oocourse.spec3.exceptions.InvalidTypeException;
import com.oocourse.spec3.exceptions.NoContributorsException;
import com.oocourse.spec3.exceptions.NoUserException;
import com.oocourse.spec3.exceptions.NoVideoUploadedException;
import com.oocourse.spec3.exceptions.SelfSubscriptionException;
import com.oocourse.spec3.exceptions.UncessException;
import com.oocourse.spec3.exceptions.UserIdNotFoundException;
import com.oocourse.spec3.exceptions.VideoIdNotFoundException;
import com.oocourse.spec3.exceptions.VideoUnwatchedException;
import com.oocourse.spec3.main.NetworkInterface;
import com.oocourse.spec3.main.UserInterface;
import com.oocourse.spec3.main.VideoInterface;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

public class Network implements NetworkInterface {

    private final Map<Integer, User> userMap = new HashMap<>();
    private final Map<Integer, Video> videoMap = new HashMap<>();
    private final Map<String, TreeSet<Video>> typeHotRank = new HashMap<>();

    private int mutualFollowingSum = 0;
    private boolean longestDirty = true;
    private int longestDecSeqCache = 0;

    public Network() {
    }

    private User getUserOrThrow(int userId) throws UserIdNotFoundException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        return user;
    }

    private Video getVideoOrThrow(int videoId) throws VideoIdNotFoundException {
        Video video = videoMap.get(videoId);
        if (video == null) {
            throw new VideoIdNotFoundException(videoId);
        }
        return video;
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

    private void beforeVideoHeatChange(Video video) {
        String type = video.getType();
        TreeSet<Video> set = typeHotRank.get(type);
        if (set != null) {
            set.remove(video);
        }
    }

    private void afterVideoHeatChange(Video video, int heatDelta) {
        String type = video.getType();
        typeHotRank.computeIfAbsent(type, k -> new TreeSet<>((v1, v2) -> {
            if (v1.getHeat() != v2.getHeat()) {
                return Integer.compare(v2.getHeat(), v1.getHeat());
            }
            return Integer.compare(v1.getId(), v2.getId());
        })).add(video);
        User uploader = userMap.get(video.getUploaderId());
        if (uploader != null) {
            uploader.updateInfluence(type, heatDelta);
        }
    }

    @Override
    public void uploadVideo(int uploaderId, int videoId, String type)
        throws UserIdNotFoundException, EqualVideoIdException, InvalidTypeException {
        final User uploader = getUserOrThrow(uploaderId);
        if (containsVideo(videoId)) {
            throw new EqualVideoIdException(videoId);
        }
        if (!isValidType(type)) {
            throw new InvalidTypeException(type);
        }
        Video video = new Video(videoId, uploaderId, type);
        videoMap.put(videoId, video);
        uploader.addVideo(video);
        afterVideoHeatChange(video, 0);
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
        User user1 = getUserOrThrow(id1);
        User user2 = getUserOrThrow(id2);
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
        User user1 = getUserOrThrow(id1);
        User user2 = getUserOrThrow(id2);
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
        User user = getUserOrThrow(userId);
        Video video = getVideoOrThrow(videoId);
        user.watchVideo(video);
        beforeVideoHeatChange(video);
        video.addPlayCount();
        afterVideoHeatChange(video, 2);
        System.out.println("watch_video succeeded");
    }

    @Override
    public List<Integer> queryReceivedUnwatchedVideos(int userId)
        throws UserIdNotFoundException {
        User user = getUserOrThrow(userId);
        return user.queryReceivedUnwatchedVideos();
    }

    @Override
    public double[] queryUpFollowersAgeRatio(int upId)
        throws UserIdNotFoundException {
        User up = getUserOrThrow(upId);
        return up.queryAgeRatio();
    }

    @Override
    public int queryMutualFollowingSum() {
        return mutualFollowingSum;
    }

    @Override
    public int queryShortestPath(int id1, int id2)
        throws UserIdNotFoundException, UncessException {
        getUserOrThrow(id1);
        getUserOrThrow(id2);
        if (id1 == id2) {
            return 0;
        }
        return NetworkHelper.bfsShortestPath(userMap, id1, id2);
    }

    @Override
    public void addUserCoins(int userId, int coins) throws UserIdNotFoundException {
        User user = getUserOrThrow(userId);
        user.addCoins(coins);
        System.out.println("add_user_coins succeeded");
    }

    @Override
    public void likeVideo(int userId, int videoId)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        VideoUnwatchedException, EqualUserIdException {
        User user = getUserOrThrow(userId);
        Video video = getVideoOrThrow(videoId);
        if (userId == video.getUploaderId()) {
            throw new EqualUserIdException(userId);
        }
        if (!user.hasWatchedVideo(video)) {
            throw new VideoUnwatchedException(userId, videoId);
        }
        if (user.hasLikedVideo(video)) {
            user.unlikeVideo(video);
            beforeVideoHeatChange(video);
            video.removeLike();
            afterVideoHeatChange(video, -3);
            System.out.println("unlike_video succeeded");
        } else {
            user.likeVideo(video);
            beforeVideoHeatChange(video);
            video.addLike();
            afterVideoHeatChange(video, 3);
            System.out.println("like_video succeeded");
        }
    }

    @Override
    public void coinVideo(int userId, int videoId, int amount)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        InsufficientCoinsException, VideoUnwatchedException,
        InvalidCoinsException, EqualUserIdException {
        User user = getUserOrThrow(userId);
        Video video = getVideoOrThrow(videoId);
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
        beforeVideoHeatChange(video);
        video.addCoins(amount);
        afterVideoHeatChange(video, 5 * amount);
        System.out.println("coin_video succeeded");
    }

    @Override
    public int queryBestContributor(int id)
        throws UserIdNotFoundException, NoContributorsException {
        User user = getUserOrThrow(id);
        if (!user.hasContributors()) {
            throw new NoContributorsException(id);
        }
        return user.queryBestContributor();
    }

    @Override
    public void forwardVideo(int userId, int videoId, int followerId)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        FollowLinkNotFoundException, VideoUnwatchedException {
        User user = getUserOrThrow(userId);
        User follower = getUserOrThrow(followerId);
        Video video = getVideoOrThrow(videoId);
        if (!user.hasWatchedVideo(video)) {
            throw new VideoUnwatchedException(userId, videoId);
        }
        if (!user.containsFollower(follower)) {
            throw new FollowLinkNotFoundException(userId, followerId);
        }
        follower.receiveVideo(videoId);
        beforeVideoHeatChange(video);
        video.addForwardCount();
        afterVideoHeatChange(video, 4);
        System.out.println("forward_video succeeded");
    }

    @Override
    public void sendComment(int userId, int videoId, int commentId, String comment)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        EqualCommentIdException, InvalidCommentException {
        getUserOrThrow(userId);
        Video video = getVideoOrThrow(videoId);
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
        Video video = getVideoOrThrow(videoId);
        return video.cleanSpamComments(keyword);
    }

    @Override
    public VideoInterface queryMostPopularVideo(String type)
        throws InvalidTypeException {
        if (!isValidType(type)) {
            throw new InvalidTypeException(type);
        }
        TreeSet<Video> set = typeHotRank.get(type);
        if (set == null || set.isEmpty()) {
            return null;
        }
        return set.first();
    }

    @Override
    public void purchaseMedal(int userId, int videoId, int amount)
        throws UserIdNotFoundException, VideoIdNotFoundException,
        EqualUserIdException, InsufficientCoinsException, DuplicateMedalException {
        User user = getUserOrThrow(userId);
        Video video = getVideoOrThrow(videoId);
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
        longestDecSeqCache = NetworkHelper.calculateLongestDecSeq(userMap);
        longestDirty = false;
        return longestDecSeqCache;
    }

    @Override
    public int[] queryGlobalBestContributor() throws NoUserException {
        if (userMap.isEmpty()) {
            throw new NoUserException();
        }
        return NetworkHelper.queryGlobalBestContributor(userMap);
    }

    @Override
    public int recommendVideo(int userId)
        throws UserIdNotFoundException, NoVideoUploadedException, ColdStartVideoException {
        User user = getUserOrThrow(userId);
        if (videoMap.isEmpty()) {
            throw new NoVideoUploadedException();
        }
        if (user.getWatchedVideoIds().isEmpty()) {
            throw new ColdStartVideoException(userId);
        }
        int bestId = Integer.MAX_VALUE;
        long maxScore = -1;
        for (Video video : videoMap.values()) {
            long score = computeVideoScore(user, video);
            if (score > maxScore || (score == maxScore && video.getId() < bestId)) {
                maxScore = score;
                bestId = video.getId();
            }
        }
        return bestId;
    }

    @Override
    public long computeVideoScore(UserInterface user, VideoInterface video) {
        return (long) video.getHeat() * user.getInterest(video.getType(), videoMap.size());
    }

    @Override
    public int recommendNthUp(int userId, int rank)
        throws UserIdNotFoundException, InvalidRankException,
        NoVideoUploadedException, ColdStartUserException {
        User user = getUserOrThrow(userId);
        if (rank <= 0) {
            throw new InvalidRankException(rank);
        }
        if (videoMap.isEmpty()) {
            throw new NoVideoUploadedException();
        }

        List<User> candidates = new ArrayList<>();
        for (User candidate : userMap.values()) {
            if (candidate.getId() != userId && !user.isFollowing(candidate)) {
                candidates.add(candidate);
            }
        }

        if (candidates.size() < rank) {
            throw new ColdStartUserException(userId);
        }

        int totalVideos = videoMap.size();
        List<NetworkHelper.UpScore> scores = new ArrayList<>(candidates.size());
        for (User c : candidates) {
            scores.add(new NetworkHelper.UpScore(c.getId(), user.computeUpScore(c, totalVideos)));
        }

        return NetworkHelper.fastSelect(scores, 0, scores.size() - 1, rank);
    }

    @Override
    public int queryMostInfluentialUp(String type) throws InvalidTypeException, NoUserException {
        if (!isValidType(type)) {
            throw new InvalidTypeException(type);
        }
        if (userMap.isEmpty()) {
            throw new NoUserException();
        }

        return NetworkHelper.queryMostInfluentialUp(userMap, type);
    }

    @Override
    public List<Integer> queryUserProfile(int userId)
        throws UserIdNotFoundException, ColdStartVideoException {
        User user = getUserOrThrow(userId);
        if (user.getWatchedVideoIds().isEmpty()) {
            throw new ColdStartVideoException(userId);
        }

        return user.getProfile(videoMap.size());
    }

    public UserInterface[] getUsers() {
        return userMap.values().toArray(new UserInterface[0]);
    }

}
