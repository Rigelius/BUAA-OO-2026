package com.oocourse.spec2.main;

import com.oocourse.spec2.exceptions.EqualCommentIdException;
import com.oocourse.spec2.exceptions.InsufficientCoinsException;
import com.oocourse.spec2.exceptions.NoContributorsException;
import com.oocourse.spec2.exceptions.SelfSubscriptionException;
import com.oocourse.spec2.exceptions.VideoUnwatchedException;
import com.oocourse.spec2.exceptions.EqualUserIdException;
import com.oocourse.spec2.exceptions.EqualVideoIdException;
import com.oocourse.spec2.exceptions.FollowLinkNotFoundException;
import com.oocourse.spec2.exceptions.InvalidAgeException;
import com.oocourse.spec2.exceptions.InvalidCoinsException;
import com.oocourse.spec2.exceptions.InvalidCommentException;
import com.oocourse.spec2.exceptions.InvalidTypeException;
import com.oocourse.spec2.exceptions.UncessException;
import com.oocourse.spec2.exceptions.UserIdNotFoundException;
import com.oocourse.spec2.exceptions.VideoIdNotFoundException;
import com.oocourse.spec2.exceptions.DuplicateSubscriptionException;
import com.oocourse.spec2.exceptions.DuplicateMedalException;

import java.util.List;

public interface NetworkInterface {
    /*@ public instance model non_null UserInterface[] users;
      @ public instance model non_null VideoInterface[] videos;
      @*/

    /*@ invariant (\forall int i,j; 0 <= i && i < j && j < users.length;
      @   !users[i].equals(users[j])) &&
      @  (\forall int i,j; 0 <= i && i < j && j < videos.length;
      @   !videos[i].equals(videos[j]))
      @*/

    //@ ensures \result == (\exists int i; 0 <= i && i < users.length; users[i].getId() == id);
    public /*@ pure @*/ boolean containsUser(int id);

    /*@ public normal_behavior
      @ requires containsUser(id);
      @ ensures (\exists int i; 0 <= i && i < users.length; users[i].getId() == id && \result == users[i]);
      @ also
      @ public normal_behavior
      @ requires !containsUser(id);
      @ ensures \result == null;
      @*/
    public /*@ pure @*/ UserInterface getUser(int id);

    //@ ensures \result == (\exists int i; 0 <= i && i < videos.length; videos[i].getId() == id);
    public /*@ pure @*/ boolean containsVideo(int id);

    /*@ public normal_behavior
      @ requires containsVideo(id);
      @ ensures (\exists int i; 0 <= i && i < videos.length; videos[i].getId() == id && \result == videos[i]);
      @ also
      @ public normal_behavior
      @ requires !containsVideo(id);
      @ ensures \result == null;
      @*/
    public /*@ pure @*/ VideoInterface getVideo(int id);

    /*@ public normal_behavior
      @ requires !containsUser(id) && age >= 0 && age <= 110;
      @ assignable users;
      @ ensures containsUser(id);
      @ ensures getUser(id).getId() == id;
      @ ensures getUser(id).getName().equals(name);
      @ ensures getUser(id).getAge() == age;
      @ ensures getUser(id).getCoins() == 0;
      @ ensures getUser(id).following.length == 0;
      @ ensures getUser(id).followers.length == 0;
      @ ensures getUser(id).receivedVideos.length == 0;
      @ ensures getUser(id).contributors.length == 0;
      @ ensures getUser(id).contributions.length == 0;
      @ ensures getUser(id).watchedVideos.length == 0;
      @ ensures getUser(id).likedVideos.length == 0;
      @ ensures getUser(id).medals.length == 0;
      @ ensures (* output-> "add_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (EqualUserIdException e) containsUser(id);
      @ signals (InvalidAgeException e) !containsUser(id) && (age < 0 || age > 110);
      @*/
    public /*@ safe @*/ void addUser(int id, String name, int age) throws EqualUserIdException, InvalidAgeException;

    /*@ public normal_behavior
      @ requires containsUser(uploaderId) && !containsVideo(videoId) && isValidType(type);
      @ assignable videos, users[*].receivedVideos;
      @ ensures containsVideo(videoId);
      @ ensures getVideo(videoId).getId() == videoId;
      @ ensures getVideo(videoId).getUploaderId() == uploaderId;
      @ ensures getVideo(videoId).getType().equals(type);
      @ ensures getVideo(videoId).getPlayCount() == 0;
      @ ensures getVideo(videoId).getLikes() == 0;
      @ ensures getVideo(videoId).getForwardCount() == 0;
      @ ensures getVideo(videoId).getCoins() == 0;
      @ ensures getVideo(videoId).commentIds.length == 0;
      @ ensures getVideo(videoId).commentContents.length == 0;
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); u.receivedVideos[0] == videoId);
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); (\forall int i; 0 <= i && i < \old(u.receivedVideos.length);
      @                                                                         u.receivedVideos[i + 1] == \old(u.receivedVideos[i])));
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); u.receivedVideos.length == \old(u.receivedVideos.length) + 1);
      @ ensures (* output-> "upload_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(uploaderId);
      @ signals (EqualVideoIdException e) containsUser(uploaderId) && containsVideo(videoId);
      @ signals (InvalidTypeException e) containsUser(uploaderId) && !containsVideo(videoId) && !isValidType(type);
      @*/
    public /*@ safe @*/ void uploadVideo(int uploaderId, int videoId, String type) throws UserIdNotFoundException, EqualVideoIdException, InvalidTypeException;

    //@ ensures \result == (type.equals("tech") || type.equals("music") || type.equals("sport") || type.equals("game") || type.equals("food") || type.equals("travel") || type.equals("comedy"));
    public /*@ pure @*/boolean isValidType(String type);

    /*@ public normal_behavior
      @ requires containsUser(id1) && containsUser(id2) && id1 != id2 && !getUser(id1).isFollowing(getUser(id2));
      @ assignable users[*];
      @ ensures getUser(id1).isFollowing(getUser(id2));
      @ ensures getUser(id2).containsFollower(getUser(id1));
      @ ensures (* output-> "follow_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) && !containsUser(id2);
      @ signals (SelfSubscriptionException e) containsUser(id1) && containsUser(id2) && id1 == id2;
      @ signals (DuplicateSubscriptionException e) containsUser(id1) && containsUser(id2) && id1 != id2 && getUser(id1).isFollowing(getUser(id2));
      @*/
    public /*@ safe @*/ void followUser(int id1, int id2) throws UserIdNotFoundException, SelfSubscriptionException, DuplicateSubscriptionException;

    /*@ public normal_behavior
      @ requires containsUser(id1) && containsUser(id2) && getUser(id1).isFollowing(getUser(id2));
      @ assignable users[*];
      @ ensures !getUser(id1).isFollowing(getUser(id2));
      @ ensures !getUser(id2).containsFollower(getUser(id1));
      @ ensures (* output-> "unfollow_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) && !containsUser(id2);
      @ signals (FollowLinkNotFoundException e) containsUser(id1) && containsUser(id2) && !getUser(id1).isFollowing(getUser(id2));
      @*/
    public /*@ safe @*/ void unfollowUser(int id1, int id2) throws UserIdNotFoundException, FollowLinkNotFoundException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId);
      @ assignable getUser(userId).receivedVideos, getUser(userId).watchedVideos, getVideo(videoId).playCount;
      @ ensures !getUser(userId).hasReceivedVideo(getVideo(videoId));
      @ ensures getUser(userId).hasWatchedVideo(getVideo(videoId));
      @ ensures getVideo(videoId).getPlayCount() == \old(getVideo(videoId).getPlayCount()) + 1;
      @ ensures (* output-> "watch_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @*/
    public /*@ safe @*/ void watchVideo(int userId, int videoId) throws UserIdNotFoundException, VideoIdNotFoundException;

    /*@ public normal_behavior
      @ requires containsUser(userId);
      @ assignable \nothing;
      @ ensures \result == getUser(userId).queryReceivedUnwatchedVideos();
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @*/
    public /*@ pure @*/ List<Integer> queryReceivedUnwatchedVideos(int userId) throws UserIdNotFoundException;

    /*@ public normal_behavior
      @ requires containsUser(upId);
      @ assignable \nothing;
      @ ensures \result == getUser(upId).queryAgeRatio();
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(upId);
      @*/
    public /*@ pure @*/ double[] queryUpFollowersAgeRatio(int upId) throws UserIdNotFoundException;

    /*@ ensures \result == (\sum int i; 0 <= i && i < users.length;
      @          (\sum int j; i < j && j < users.length;
      @           (users[i].isFollowing(users[j]) && users[j].isFollowing(users[i])) ? 1 : 0));
      @*/
    public /*@ pure @*/ int queryMutualFollowingSum();

    /*@ public normal_behavior
      @ requires containsUser(id1) && id1 == id2;
      @ ensures \result == 0;
      @ also
      @ public normal_behavior
      @ requires containsUser(id1) &&
      @          containsUser(id2) &&
      @          id1 != id2 &&
      @          (\exists UserInterface[] path;
      @          path.length >= 2 &&
      @          path[0].equals(getUser(id1)) &&
      @          path[path.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i])));
      @ ensures  (\exists UserInterface[] pathM;
      @          pathM.length >= 2 &&
      @          pathM[0].equals(getUser(id1)) &&
      @          pathM[pathM.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < pathM.length; pathM[i - 1].isFollowing(pathM[i]));
      @          (\forall UserInterface[] path;
      @          path.length >= 2 &&
      @          path[0].equals(getUser(id1)) &&
      @          path[path.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i]));
      @          (\sum int i; 0 <= i && i < path.length; 1) >=
      @          (\sum int i; 0 <= i && i < pathM.length; 1)) &&
      @          \result==(\sum int i; 1 <= i && i < pathM.length; 1));
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) && !containsUser(id2);
      @ signals (UncessException e) containsUser(id1) && containsUser(id2) && id1 != id2 &&
      @         !(\exists UserInterface[] path; path.length >= 2 && path[0].equals(getUser(id1)) && path[path.length - 1].equals(getUser(id2));
      @             (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i])));
      @*/
    public /*@ pure @*/ int queryShortestPath(int id1, int id2) throws UserIdNotFoundException, UncessException;

    /*@ public normal_behavior
      @ requires containsUser(userId)
      @ assignable getUser(userId).coins
      @ ensures getUser(userId).getCoins() == \old(getUser(userId).getCoins()) + coins;
      @ ensures (* output-> "add_user_coins succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
     */
    public /*@ safe @*/ void addUserCoins(int userId, int coins) throws UserIdNotFoundException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).hasWatchedVideo(getVideo(videoId)) && !getUser(userId).hasLikedVideo(getVideo(videoId));
      @ assignable getVideo(videoId).likes, getUser(userId).likedVideos;
      @ ensures getUser(userId).hasLikedVideo(getVideo(videoId));
      @ ensures getVideo(videoId).getLikes() == \old(getVideo(videoId).getLikes()) + 1
      @ ensures (* output-> "like_video succeeded" *);
      @ also
      @ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).hasWatchedVideo(getVideo(videoId)) && getUser(userId).hasLikedVideo(getVideo(videoId));
      @ assignable getVideo(videoId).likes, getUser(userId).likedVideos;
      @ ensures !getUser(userId).hasLikedVideo(getVideo(videoId));
      @ ensures getVideo(videoId).getLikes() == \old(getVideo(videoId).getLikes()) - 1
      @ ensures (* output-> "unlike_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @ signals (EqualUserIdException e) containsUser(userId) && containsVideo(videoId) && userId == getVideo(videoId).getUploaderId();
      @ signals (VideoUnwatchedException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && !getUser(userId).hasWatchedVideo(getVideo(videoId))
      @*/
    public /*@ safe @*/ void likeVideo(int userId, int videoId) throws UserIdNotFoundException, VideoIdNotFoundException, VideoUnwatchedException, EqualUserIdException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId()
      @         && getUser(userId).hasWatchedVideo(getVideo(videoId)) && (amount == 1 || amount == 2) && getUser(userId).getCoins() >= amount
      @         && !(\exists int i; 0 <= i && i < getUser(getVideo(videoId).getUploaderId()).contributors.length;
      @                 getUser(getVideo(videoId).getUploaderId()).contributors[i].getId() == userId);
      @ assignable getVideo(videoId).coins, getUser(userId).coins,
      @            getUser(getVideo(videoId).getUploaderId()).coins,
      @            getUser(getVideo(videoId).getUploaderId()).contributors,
      @            getUser(getVideo(videoId).getUploaderId()).contributions;
      @ ensures getVideo(videoId).getCoins() == \old(getVideo(videoId).getCoins()) + amount;
      @ ensures getUser(userId).getCoins() == \old(getUser(userId).getCoins()) - amount;
      @ ensures getUser(getVideo(videoId).getUploaderId()).getCoins() == \old(getUser(getVideo(videoId).getUploaderId()).getCoins()) + amount;
      @ ensures getUser(getVideo(videoId).getUploaderId()).contributors.length == \old(getUser(getVideo(videoId).getUploaderId()).contributors.length) + 1;
      @ ensures (\exists int i; 0 <= i && i < getUser(getVideo(videoId).getUploaderId()).contributors.length;
      @                 getUser(getVideo(videoId).getUploaderId()).contributors[i].equals(getUser(userId))
                        && getUser(getVideo(videoId).getUploaderId()).contributions[i] == amount);
      @ ensures (* output-> "coin_video succeeded" *);
      @ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId()
      @         && getUser(userId).hasWatchedVideo(getVideo(videoId)) && (amount == 1 || amount == 2) && getUser(userId).getCoins() >= amount
      @         && (\exists int i; 0 <= i && i < getUser(getVideo(videoId).getUploaderId()).contributors.length;
      @                 getUser(getVideo(videoId).getUploaderId()).contributors[i].getId() == userId);
      @ assignable getVideo(videoId).coins, getUser(userId).coins,
      @            getUser(getVideo(videoId).getUploaderId()).coins,
      @            getUser(getVideo(videoId).getUploaderId()).contributions;
      @ ensures getVideo(videoId).getCoins() == \old(getVideo(videoId).getCoins()) + amount;
      @ ensures getUser(userId).getCoins() == \old(getUser(userId).getCoins()) - amount;
      @ ensures getUser(getVideo(videoId).getUploaderId()).getCoins() == \old(getUser(getVideo(videoId).getUploaderId()).getCoins()) + amount;
      @ ensures (\exists int i; 0 <= i && i < getUser(getVideo(videoId).getUploaderId()).contributors.length;
      @                 getUser(getVideo(videoId).getUploaderId()).contributors[i].equals(getUser(userId))
                        && getUser(getVideo(videoId).getUploaderId()).contributions[i] == \old(getUser(getVideo(videoId).getUploaderId()).contributions[i]) + amount);
      @ ensures (* output-> "coin_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @ signals (EqualUserIdException e) containsUser(userId) && containsVideo(videoId) && userId == getVideo(videoId).getUploaderId();
      @ signals (VideoUnwatchedException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && !getUser(userId).hasWatchedVideo(getVideo(videoId));
      @ signals (InvalidCoinsException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).hasWatchedVideo(getVideo(videoId)) && amount != 1 && amount != 2;
      @ signals (InsufficientCoinsException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).hasWatchedVideo(getVideo(videoId)) && (amount == 1 || amount == 2) && getUser(userId).getCoins() < amount;
      @*/
    public /*@ safe @*/ void coinVideo(int userId, int videoId, int amount) throws UserIdNotFoundException, VideoIdNotFoundException, InsufficientCoinsException, VideoUnwatchedException, InvalidCoinsException, EqualUserIdException;

    /*@ public normal_behavior
      @ requires containsUser(id) && getUser(id).contributors.length > 0;
      @ assignable \nothing;
      @ ensures \result == (\min int bestId;
      @                         (\exists int i; 0 <= i && i < getUser(id).contributors.length; getUser(id).contributors[i].id == bestId &&
      @                             (\forall int j; 0 <= j && j < getUser(id).contributors.length; getUser(id).contributions[i] >= getUser(id).contributions[j]));
      @                         bestId);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id);
      @ signals (NoContributorsException e) containsUser(id) && getUser(id).contributors.length == 0;
     */
    public /*@ pure @*/ int queryBestContributor(int id) throws UserIdNotFoundException, NoContributorsException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsUser(followerId) && containsVideo(videoId) && getUser(userId).hasWatchedVideo(getVideo(videoId)) && getUser(userId).containsFollower(getUser(followerId));
      @ assignable getUser(followerId).receivedVideos, getVideo(videoId).forwardCount;
      @ ensures getUser(followerId).receivedVideos[0] == videoId;
      @ ensures (\forall int i; 0 <= i && i < \old(getUser(followerId).receivedVideos.length); getUser(followerId).receivedVideos[i + 1] == \old(getUser(followerId).receivedVideos[i]));
      @ ensures getUser(followerId).receivedVideos.length == \old(getUser(followerId).receivedVideos.length) + 1;
      @ ensures getVideo(videoId).getForwardCount() == \old(getVideo(videoId).getForwardCount()) + 1;
      @ ensures (* output-> "forward_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (UserIdNotFoundException e) containsUser(userId) && !containsUser(followerId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && containsUser(followerId) && !containsVideo(videoId);
      @ signals (VideoUnwatchedException e) containsUser(userId) && containsUser(followerId) && containsVideo(videoId) && !getUser(userId).hasWatchedVideo(getVideo(videoId));
      @ signals (FollowLinkNotFoundException e) containsUser(userId) && containsUser(followerId) && containsVideo(videoId) && getUser(userId).hasWatchedVideo(getVideo(videoId)) && !getUser(userId).containsFollower(getUser(followerId));
     */
    public /*@ safe @*/ void forwardVideo(int userId, int videoId, int followerId) throws UserIdNotFoundException, VideoIdNotFoundException, FollowLinkNotFoundException, VideoUnwatchedException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && !getVideo(videoId).containsComment(commentId) && comment != null && !comment.equals("");
      @ assignable getVideo(videoId).commentIds, getVideo(videoId).commentContents;
      @ ensures (\exists int i; 0 <= i && i < getVideo(videoId).commentIds.length;
      @              getVideo(videoId).commentIds[i] == commentId &&
      @              getVideo(videoId).commentContents[i].equals(comment));
      @ ensures (* output-> "send_comment succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @ signals (EqualCommentIdException e) containsUser(userId) && containsVideo(videoId) && getVideo(videoId).containsComment(commentId);
      @ signals (InvalidCommentException e) containsUser(userId) && containsVideo(videoId) && !getVideo(videoId).containsComment(commentId) && (comment == null || comment.equals(""));
     */
    public /*@ safe @*/ void sendComment(int userId, int videoId, int commentId, String comment) throws UserIdNotFoundException, VideoIdNotFoundException, EqualCommentIdException, InvalidCommentException;

    /*@ public normal_behavior
      @ requires containsVideo(videoId);
      @ assignable getVideo(videoId).commentIds, getVideo(videoId).commentContents;
      @ ensures \result.length == 2;
      @ ensures \result[0] == (\num_of int i; 0 <= i < \old(getVideo(videoId).commentIds.length);\old(getVideo(videoId).commentContents[i]).contains(keyword));
      @ ensures getVideo(videoId).commentIds.length == \old(getVideo(videoId).commentIds.length) - \result[0];
      @ ensures (\forall int i; 0 <= i < getVideo(videoId).commentIds.length; !getVideo(videoId).commentContents[i].contains(keyword));
      @ ensures (\forall int j; 0 <= j < \old(getVideo(videoId).commentIds.length);
      @             !\old(getVideo(videoId).commentContents[j]).contains(keyword) ==>
      @                     (\exists int i; 0 <= i < getVideo(videoId).commentIds.length;
      @                         getVideo(videoId).commentIds[i] == \old(getVideo(videoId).commentIds[j]) &&
      @                             getVideo(videoId).commentContents[i].equals(\old(getVideo(videoId).commentContents[j]))));
      @ ensures (\result[0] == 0) ==> (\result[1] == 0);
      @ ensures (\result[0] > 0) ==> (\result[1] == (\max int i; 0 <= i < \old(getVideo(videoId).commentIds.length) &&
      @                                 (\exists int j;
      @                                     0 <= j && j + keyword.length() <= \old(getVideo(videoId).commentContents[i].length());
      @                                     \old(getVideo(videoId).commentContents[i]).substring(j, j+keyword.length()).equals(keyword));
      @                                 (\num_of int j;
      @                                     0 <= j && j + keyword.length() <= \old(getVideo(videoId).commentContents[i].length());
      @                                     \old(getVideo(videoId).commentContents[i]).substring(j, j+keyword.length()).equals(keyword))));
      @ also
      @ public exceptional_behavior
      @ signals (VideoIdNotFoundException e) !containsVideo(videoId);
     */
    public /*@ safe @*/ int[] cleanSpamComments(int videoId, String keyword) throws VideoIdNotFoundException;

    /*@ public normal_behavior
      @ requires isValidType(type);
      @ requires (\sum int i; 0 <= i && i < videos.length && videos[i].getType().equals(type); 1) != 0;
      @ assignable \nothing;
      @ ensures \result != null && \result.getType().equals(type);
      @ ensures (\result == getVideo((\min int bestId;
      @                         (\exists int i; 0 <= i && i < videos.length; videos[i].getId() == bestId && videos[i].getType().equals(type) &&
      @                             (\forall int j; 0 <= j && j < videos.length; videos[j].getType().equals(type) ==> videos[j].getHeat() <= videos[i].getHeat()));
      @                                 bestId)));
      @ public normal_behavior
      @ requires isValidType(type);
      @ requires (\sum int i; 0 <= i && i < videos.length && videos[i].getType().equals(type); 1) == 0;
      @ assignable \nothing;
      @ ensures \result == null;
      @ also
      @ public exceptional_behavior
      @ signals (InvalidTypeException e) !isValidType(type);
     */
    public /* pure */ VideoInterface queryMostPopularVideo(String type) throws InvalidTypeException;

    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).getCoins() >= amount && !getUser(userId).hasMedal(getVideo(videoId).getUploaderId());
      @ assignable getUser(userId).coins, getUser(getVideo(videoId).getUploaderId()).coins, getUser(userId).medals;
      @ ensures getUser(userId).getCoins() == \old(getUser(userId).getCoins()) - amount;
      @ ensures getUser(userId).hasMedal(getVideo(videoId).getUploaderId());
      @ ensures getUser(getVideo(videoId).getUploaderId()).getCoins() == \old(getUser(getVideo(videoId).getUploaderId()).getCoins()) + amount;
      @ ensures (* output-> "purchase_medal succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @ signals (EqualUserIdException e) containsUser(userId) && containsVideo(videoId) && userId == getVideo(videoId).getUploaderId();
      @ signals (InsufficientCoinsException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).getCoins() < amount;
      @ signals (DuplicateMedalException e) containsUser(userId) && containsVideo(videoId) && userId != getVideo(videoId).getUploaderId() && getUser(userId).getCoins() >= amount && getUser(userId).hasMedal(getVideo(videoId).getUploaderId());
      @*/
    public /*@ safe @*/ void purchaseMedal(int userId, int videoId, int amount) throws
            UserIdNotFoundException, VideoIdNotFoundException, EqualUserIdException,
            InsufficientCoinsException, DuplicateMedalException;

    /*@ public normal_behavior
      @ requires users.length == 0;
      @ ensures \result == 0;
      @ also
      @ public normal_behavior
      @ requires users.length > 0;
      @ ensures (\exists UserInterface[] pathMax;
      @         pathMax.length >= 1 &&
      @         (\forall int i; 0 <= i && i < pathMax.length; containsUser(pathMax[i].getId())) &&
      @         (\forall int i; 1 <= i && i < pathMax.length; pathMax[i - 1].isFollowing(pathMax[i])) &&
      @         (\forall int i; 1 <= i && i < pathMax.length; pathMax[i - 1].getAge() > pathMax[i].getAge());
      @         (\forall UserInterface[] path;
      @             path.length >= 1 &&
      @             (\forall int j; 0 <= j && j < path.length; containsUser(path[j].getId())) &&
      @             (\forall int j; 1 <= j && j < path.length; path[j - 1].isFollowing(path[j])) &&
      @             (\forall int j; 1 <= j && j < path.length; path[j - 1].getAge() > path[j].getAge());
      @             path.length <= pathMax.length) &&
      @         \result == pathMax.length);
      @*/
    public /*@ pure @*/ int queryLongestDecSeq();

}
