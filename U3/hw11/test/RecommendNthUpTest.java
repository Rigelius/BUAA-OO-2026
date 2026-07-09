import com.oocourse.spec3.exceptions.ColdStartUserException;
import com.oocourse.spec3.exceptions.InvalidRankException;
import com.oocourse.spec3.exceptions.NoVideoUploadedException;
import com.oocourse.spec3.exceptions.UserIdNotFoundException;
import com.oocourse.spec3.main.UserInterface;
import com.oocourse.spec3.main.VideoInterface;
import org.junit.Test;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class RecommendNthUpTest {
    private static final String[] TYPES = {
        "tech", "music", "sport", "game", "food", "travel", "comedy"
    };
    private static final int[] RICH_USERS = {1, 2, 3, 4, 5, 6};
    private static final int[] RICH_VIDEOS = {201, 301, 401, 501};
    private static final int[] UP_IDS = {2, 3, 4, 5, 6};

    @Test
    public void testNormalRanksAndTieBreak() throws Exception {
        Network network = rankingNetwork();

        assertRecommend(network, 1, 1, 2, RICH_USERS, RICH_VIDEOS, UP_IDS);
        assertRecommend(network, 1, 2, 3, RICH_USERS, RICH_VIDEOS, UP_IDS);
        assertRecommend(network, 1, 3, 4, RICH_USERS, RICH_VIDEOS, UP_IDS);
        assertRecommend(network, 1, 4, 5, RICH_USERS, RICH_VIDEOS, UP_IDS);
        assertRecommend(network, 1, 5, 6, RICH_USERS, RICH_VIDEOS, UP_IDS);
    }

    @Test
    public void testFollowedUsersAreExcluded() throws Exception {
        Network network = rankingNetwork();
        network.followUser(1, 2);

        assertRecommend(network, 1, 1, 3, RICH_USERS, RICH_VIDEOS, UP_IDS);
        assertRecommend(network, 1, 2, 4, RICH_USERS, RICH_VIDEOS, UP_IDS);
    }

    @Test
    public void testUserIdNotFoundHasHighestPriority() throws Exception {
        Network network = rankingNetwork();
        NetworkSnapshot before = takeSnapshot(network, RICH_USERS, RICH_VIDEOS, UP_IDS);

        try {
            network.recommendNthUp(999, 0);
            fail("Expected UserIdNotFoundException");
        } catch (UserIdNotFoundException e) {
            assertStateUnchanged(before, network, RICH_USERS, RICH_VIDEOS, UP_IDS);
        }
    }

    @Test
    public void testInvalidRankBeforeNoVideoUploaded() throws Exception {
        Network network = new Network();
        network.addUser(1, "A", 20);
        network.addUser(2, "B", 21);
        int[] users = {1, 2};
        int[] videos = {};
        int[] uploaders = {1, 2};
        NetworkSnapshot before = takeSnapshot(network, users, videos, uploaders);

        try {
            network.recommendNthUp(1, 0);
            fail("Expected InvalidRankException");
        } catch (InvalidRankException e) {
            assertStateUnchanged(before, network, users, videos, uploaders);
        }
    }

    @Test
    public void testNoVideoUploadedException() throws Exception {
        Network network = new Network();
        network.addUser(1, "A", 20);
        network.addUser(2, "B", 21);
        int[] users = {1, 2};
        int[] videos = {};
        int[] uploaders = {1, 2};
        NetworkSnapshot before = takeSnapshot(network, users, videos, uploaders);

        try {
            network.recommendNthUp(1, 1);
            fail("Expected NoVideoUploadedException");
        } catch (NoVideoUploadedException e) {
            assertStateUnchanged(before, network, users, videos, uploaders);
        }
    }

    @Test
    public void testColdStartUserException() throws Exception {
        Network network = rankingNetwork();
        network.followUser(1, 2);
        network.followUser(1, 3);
        network.followUser(1, 4);
        network.followUser(1, 5);
        NetworkSnapshot before = takeSnapshot(network, RICH_USERS, RICH_VIDEOS, UP_IDS);

        try {
            network.recommendNthUp(1, 2);
            fail("Expected ColdStartUserException");
        } catch (ColdStartUserException e) {
            assertStateUnchanged(before, network, RICH_USERS, RICH_VIDEOS, UP_IDS);
        }
    }

    private static void assertRecommend(Network network, int userId, int rank,
                                        int expectedId, int[] userIds,
                                        int[] videoIds, int[] uploaderIds)
        throws Exception {
        NetworkSnapshot before = takeSnapshot(network, userIds, videoIds, uploaderIds);
        int resultId = network.recommendNthUp(userId, rank);

        assertEquals(expectedId, resultId);
        assertEnsures(network, userId, rank, resultId, videoIds);
        assertStateUnchanged(before, network, userIds, videoIds, uploaderIds);
    }

    private static void assertEnsures(Network network, int userId, int rank,
                                      int resultId, int[] videoIds) {
        UserInterface queryUser = network.getUser(userId);
        UserInterface resultUser = network.getUser(resultId);
        assertTrue(network.containsUser(resultId));
        assertNotNull(resultUser);
        assertTrue(resultId != userId);
        assertFalse(queryUser.isFollowing(resultUser));

        long targetScore = queryUser.computeUpScore(resultUser, countVideos(network, videoIds));
        int betterCount = 0;
        for (UserInterface user : network.getUsers()) {
            if (user.getId() == userId || queryUser.isFollowing(user)) {
                continue;
            }
            long score = queryUser.computeUpScore(user, countVideos(network, videoIds));
            if (score > targetScore || (score == targetScore && user.getId() < resultId)) {
                betterCount++;
            }
        }
        assertEquals(rank - 1, betterCount);
    }

    private static int countVideos(Network network, int[] videoIds) {
        int count = 0;
        for (int videoId : videoIds) {
            if (network.containsVideo(videoId)) {
                count++;
            }
        }
        return count;
    }

    private static Network rankingNetwork() throws Exception {
        Network network = new Network();
        network.addUser(1, "Viewer", 20);
        network.addUser(2, "UpA", 22);
        network.addUser(3, "UpB", 24);
        network.addUser(4, "UpC", 26);
        network.addUser(5, "UpD", 28);
        network.addUser(6, "Helper", 30);

        network.uploadVideo(2, 201, "tech");
        network.uploadVideo(3, 301, "tech");
        network.uploadVideo(4, 401, "music");
        network.uploadVideo(5, 501, "game");

        network.watchVideo(1, 201);
        network.likeVideo(1, 201);
        network.watchVideo(1, 401);
        network.watchVideo(6, 301);
        return network;
    }

    private static NetworkSnapshot takeSnapshot(Network network, int[] userIds,
                                                int[] videoIds, int[] uploaderIds) {
        return new NetworkSnapshot(network, userIds, videoIds, uploaderIds);
    }

    private static void assertStateUnchanged(NetworkSnapshot before, Network network,
                                             int[] userIds, int[] videoIds,
                                             int[] uploaderIds) {
        before.assertMatches(network, userIds, videoIds, uploaderIds);
    }

    private static final class NetworkSnapshot {
        private final int userCount;
        private final Map<Integer, UserSnapshot> users = new HashMap<>();
        private final Map<Integer, VideoSnapshot> videos = new HashMap<>();

        private NetworkSnapshot(Network network, int[] userIds,
                                int[] videoIds, int[] uploaderIds) {
            userCount = network.getUsers().length;
            for (int userId : userIds) {
                users.put(userId, new UserSnapshot(network, userId, userIds,
                    videoIds, uploaderIds));
            }
            for (int videoId : videoIds) {
                videos.put(videoId, new VideoSnapshot(network, videoId));
            }
        }

        private void assertMatches(Network network, int[] userIds,
                                   int[] videoIds, int[] uploaderIds) {
            assertEquals(userCount, network.getUsers().length);
            for (int userId : userIds) {
                users.get(userId).assertMatches(network, userId, userIds,
                    videoIds, uploaderIds);
            }
            for (int videoId : videoIds) {
                videos.get(videoId).assertMatches(network, videoId);
            }
        }
    }

    private static final class UserSnapshot {
        private final boolean exists;
        private final String name;
        private final int age;
        private final int coins;
        private final double[] ageRatio;
        private final List<Integer> receivedUnwatched;
        private final List<Integer> profile;
        private final Map<Integer, Boolean> following = new HashMap<>();
        private final Map<Integer, Boolean> followers = new HashMap<>();
        private final Map<Integer, Boolean> received = new HashMap<>();
        private final Map<Integer, Boolean> watched = new HashMap<>();
        private final Map<Integer, Boolean> liked = new HashMap<>();
        private final Map<Integer, Boolean> medals = new HashMap<>();
        private final Map<String, Integer> interests = new HashMap<>();
        private final Map<String, Integer> influences = new HashMap<>();

        private UserSnapshot(Network network, int userId, int[] userIds,
                             int[] videoIds, int[] uploaderIds) {
            exists = network.containsUser(userId);
            if (!exists) {
                name = null;
                age = 0;
                coins = 0;
                ageRatio = new double[0];
                receivedUnwatched = null;
                profile = null;
                return;
            }
            UserInterface user = network.getUser(userId);
            name = user.getName();
            age = user.getAge();
            coins = user.getCoins();
            ageRatio = user.queryAgeRatio();
            receivedUnwatched = user.queryReceivedUnwatchedVideos();
            profile = user.getProfile(countVideos(network, videoIds));
            for (int otherId : userIds) {
                if (network.containsUser(otherId)) {
                    UserInterface other = network.getUser(otherId);
                    following.put(otherId, user.isFollowing(other));
                    followers.put(otherId, user.containsFollower(other));
                }
            }
            for (int videoId : videoIds) {
                if (network.containsVideo(videoId)) {
                    VideoInterface video = network.getVideo(videoId);
                    received.put(videoId, user.hasReceivedVideo(video));
                    watched.put(videoId, user.hasWatchedVideo(video));
                    liked.put(videoId, user.hasLikedVideo(video));
                }
            }
            for (int uploaderId : uploaderIds) {
                medals.put(uploaderId, user.hasMedal(uploaderId));
            }
            for (String type : TYPES) {
                interests.put(type, user.getInterest(type, countVideos(network, videoIds)));
                influences.put(type, user.getInfluence(type));
            }
        }

        private void assertMatches(Network network, int userId, int[] userIds,
                                   int[] videoIds, int[] uploaderIds) {
            assertEquals(exists, network.containsUser(userId));
            if (!exists) {
                return;
            }
            UserInterface user = network.getUser(userId);
            assertEquals(name, user.getName());
            assertEquals(age, user.getAge());
            assertEquals(coins, user.getCoins());
            assertArrayEquals(ageRatio, user.queryAgeRatio(), 1e-10);
            assertEquals(receivedUnwatched, user.queryReceivedUnwatchedVideos());
            assertEquals(profile, user.getProfile(countVideos(network, videoIds)));
            for (int otherId : userIds) {
                if (network.containsUser(otherId)) {
                    UserInterface other = network.getUser(otherId);
                    assertEquals(following.get(otherId), user.isFollowing(other));
                    assertEquals(followers.get(otherId), user.containsFollower(other));
                }
            }
            for (int videoId : videoIds) {
                if (network.containsVideo(videoId)) {
                    VideoInterface video = network.getVideo(videoId);
                    assertEquals(received.get(videoId), user.hasReceivedVideo(video));
                    assertEquals(watched.get(videoId), user.hasWatchedVideo(video));
                    assertEquals(liked.get(videoId), user.hasLikedVideo(video));
                }
            }
            for (int uploaderId : uploaderIds) {
                assertEquals(medals.get(uploaderId), user.hasMedal(uploaderId));
            }
            for (String type : TYPES) {
                assertEquals(interests.get(type).intValue(),
                    user.getInterest(type, countVideos(network, videoIds)));
                assertEquals(influences.get(type).intValue(), user.getInfluence(type));
            }
        }
    }

    private static final class VideoSnapshot {
        private final boolean exists;
        private final int uploaderId;
        private final String type;
        private final int playCount;
        private final int likes;
        private final int forwardCount;
        private final int coins;
        private final int heat;

        private VideoSnapshot(Network network, int videoId) {
            exists = network.containsVideo(videoId);
            if (!exists) {
                uploaderId = 0;
                type = null;
                playCount = 0;
                likes = 0;
                forwardCount = 0;
                coins = 0;
                heat = 0;
                return;
            }
            VideoInterface video = network.getVideo(videoId);
            uploaderId = video.getUploaderId();
            type = video.getType();
            playCount = video.getPlayCount();
            likes = video.getLikes();
            forwardCount = video.getForwardCount();
            coins = video.getCoins();
            heat = video.getHeat();
        }

        private void assertMatches(Network network, int videoId) {
            assertEquals(exists, network.containsVideo(videoId));
            if (!exists) {
                return;
            }
            VideoInterface video = network.getVideo(videoId);
            assertEquals(uploaderId, video.getUploaderId());
            assertEquals(type, video.getType());
            assertEquals(playCount, video.getPlayCount());
            assertEquals(likes, video.getLikes());
            assertEquals(forwardCount, video.getForwardCount());
            assertEquals(coins, video.getCoins());
            assertEquals(heat, video.getHeat());
        }
    }
}
