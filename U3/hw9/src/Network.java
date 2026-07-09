import com.oocourse.spec1.exceptions.DuplicateSubscriptionException;
import com.oocourse.spec1.exceptions.EqualUserIdException;
import com.oocourse.spec1.exceptions.EqualVideoIdException;
import com.oocourse.spec1.exceptions.FollowLinkNotFoundException;
import com.oocourse.spec1.exceptions.InvalidAgeException;
import com.oocourse.spec1.exceptions.SelfSubscriptionException;
import com.oocourse.spec1.exceptions.UncessException;
import com.oocourse.spec1.exceptions.UserIdNotFoundException;
import com.oocourse.spec1.exceptions.VideoIdNotFoundException;
import com.oocourse.spec1.main.NetworkInterface;
import com.oocourse.spec1.main.UserInterface;
import com.oocourse.spec1.main.VideoInterface;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Network implements NetworkInterface {

    private final Map<Integer, User> userMap = new HashMap<>();
    private final Map<Integer, Video> videoMap = new HashMap<>();

    private int mutualFollowingSum = 0;

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
    public void addUser(int id, String name, int age)
        throws EqualUserIdException, InvalidAgeException {
        if (containsUser(id)) {
            throw new EqualUserIdException(id);
        }
        if (age < 0 || age > 110) {
            throw new InvalidAgeException(age);
        }
        User user = new User(id, name, age);
        userMap.put(id, user);
        System.out.println("add_user succeeded");
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
    public void uploadVideo(int uploaderId, int videoId)
        throws UserIdNotFoundException, EqualVideoIdException {
        User uploader = userMap.get(uploaderId);
        if (uploader == null) {
            throw new UserIdNotFoundException(uploaderId);
        }
        if (containsVideo(videoId)) {
            throw new EqualVideoIdException(videoId);
        }
        Video video = new Video(videoId, uploaderId);
        videoMap.put(videoId, video);
        for (User follower : uploader.getFollowers()) {
            follower.receiveVideo(videoId);
        }
        System.out.println("upload_video succeeded");
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
        System.out.println("unfollow_user succeeded");
    }

    @Override
    public void watchVideo(int userId, int videoId)
        throws UserIdNotFoundException, VideoIdNotFoundException {
        User user = userMap.get(userId);
        if (user == null) {
            throw new UserIdNotFoundException(userId);
        }
        if (!containsVideo(videoId)) {
            throw new VideoIdNotFoundException(videoId);
        }
        user.watchVideo(videoId);
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

    public UserInterface[] getUsers() {
        return userMap.values().toArray(new UserInterface[0]);
    }
}
