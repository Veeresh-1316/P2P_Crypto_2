// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract FakeNewsDApp {
    // Struct to store news items
    struct NewsItem {
        address uploader;
        string contentHash;
        uint256 timestamp;
        string category;

        uint256 fakenessScore;
        address[] voters;
        uint totalVotes;
        mapping(address => uint256) votes;
    }
    string[] identities;

    // Mapping to store fact-checker weights, reputations and other info
    address[] private factCheckers;
    mapping(address => mapping(string => uint256)) public weights;
    mapping(address => uint) correct_votes;
    mapping(address => uint) incorrect_votes;
    mapping(address => uint256) reputations;
    mapping(address => uint) public probation;

    // Mapping to store news items, if voting period active
    mapping(string => NewsItem) public newsItems;
    mapping(string => bool) public voting;

    // list of categories
    string[] categories;

    // DEPOSIT FOR VOTING
    uint x;

    // Event emitted when a new news item is uploaded
    event NewsItemUploaded(NewsItem indexed newItem);

    // Modifier to restrict function access to registered fact-checkers
    modifier onlyFactChecker() {
        require(findFactChecker(msg.sender), "Only fact-checkers can call this function");
        _;
    }


    function findFactChecker(address _search) public view returns (bool found) {
        for (uint i = 0; i < factCheckers.length; i++) {
            if (factCheckers[i] == _search) {
                return true;
            }
        }
        return false; // Element not found
    }

    function findCategory(string _search) public view returns (bool found) {
        for (uint i = 0; i < categories.length; i++) {
            if (categories[i] == _search) {
                return true;
            }
        }
        return false; // Element not found
    }

    function findIdentity(string _search) public view returns (bool found) {
        for (uint i = 0; i < identities.length; i++) {
            if (identities[i] == _search) {
                return true;
            }
        }
        return false; // Element not found
    }


    // Add a new category
    function add_new_category(string _category) {
        categories[_category] = 1;
        for(uint i=0; i<factCheckers.length; i++) {
            weights[factCheckers[i]][_category] = 0.5;
        }
    }

    // Function to upload a news item
    function uploadNewsItem(string memory _contentHash, string _category) onlyFactChecker {
        // bytes32 itemHash = keccak256(abi.encodePacked(_contentHash, block.timestamp, msg.sender));
        string itemHash = _contentHash;
        require(newsItems[itemHash].uploader == address(0), "Item already uploaded");

        // Category can be implemented on the front-end part
        if (! findCategory(_category)) {
            add_new_category(string _category);
        }

        // add a new news item
        NewsItem memory newItem;
        newItem.uploader = msg.sender;
        newItem.contentHash = _contentHash;
        newItem.timestamp = block.timestamp;
        newItem.category = _category;
        newItem.totalVotes = 0;
        newItem.fakenessScore = -1; // INDICATE NOT YET DONE VOTING

        newsItems[itemHash] = newItem;
        emit NewsItemUploaded(newItem);
    }

    function start_voting(string _itemHash) {
        voting[_itemHash] = true;
    }
    function stop_voting(string _itemHash) {
        voting[_itemHash] = false;
        voting_results(newsItems[_itemHash]);
    }


    // Function for fact-checkers to vote on an item
    function voteOnNewsItem(string _itemHash, uint8 _vote) onlyFactChecker {
        require(newsItems[_itemHash].uploader != address(0), "Item does not exist");
        require(voting[_itemHash], "Voting Period not active");

        // --- REQUIRE A DEPOSIT OF 'x' cryptocurrency

        // store the vote
        newsItems[_itemHash].votes[msg.sender] = _vote;
        newsItems[_itemHash].totalVotes += 1;
        newsItems[_itemHash].voters.push(msg.sender);
    }


    // find results of voting of given news
    // and do necessary weight updates
    function voting_results(NewsItem news) {
        string cat = news.category;

        uint w = 0;
        for(uint i = 0; i < news.totalVotes; i++) {
            news.fakenessScore += news.votes[news.voters[i]] * weights[news.voters[i]][cat] * probation[news.voters[i]];
            w += weights[news.voters[i]][cat] * probation[news.voters[i]];
        }

        // fakeness score is weighted sum of all voters, along with their votes
        news.fakenessScore /= w;
        if(news.fakenessScore >= 0.5)
            w = 1;
        else
            w = 0;

        // classify correct and wrong voterss, for rewarding and punishing
        address[] good_addresses;
        uint good_repute = 0;
        for(uint i = 0; i < news.totalVotes; i++) {
            if(news.votes[news.voters[i]] == w) {
                good_addresses.push(news.voters[i]);
                good_repute += reputations[news.voters[i]]
                // WILL GET DEPOSIT BACK AND DISTRIBUTED REWARDS FROM WRONG VOTERS
            }
            else {
                reputations[news.voters[i]] = max(reputations[news.voters[i]]-0.5, 0);
                // NOT CONSIDERED IN DISTRIBUTING REWARDS
                // INITIAL DEPOSIT LOST
            }

            // update weights = correct / (correct + incorrect)
            weights[news.voters[i]] = correct_votes[news.voters[i]] / (correct_votes[news.voters[i]] + incorrect_votes[news.voters[i]])

        }

        // GIVE REWARD TO CORRECT VOTERS
        distribute_rewards(good_addresses, good_repute, news);
    }


    function distribute_rewards(address[] good_addresses, uint good_repute, NewsItem news) {
        // can distribute extra amount of wrong voters' deposits
        uint avail = x * (news.totalVotes - good_addresses.length);

        for(uint i = 0; i < good_addresses.length; i++) {
            uint money = x + (avail * reputations[good_addresses[i]] / good_repute)

            // --- GIVE 'money' TO good_addresses[i]

            reputations[good_addresses[i]] = min(reputations[good_addresses[i]] + 0.5, 100);
        }
    }


    // Function to get overall truthfulness score of an item
    function getTruthfulnessScore(string _itemHash) public view returns (uint256) {
        require(newsItems[_itemHash].uploader != address(0), "Item does not exist");
        return newsItems[_itemHash].fakenessScore;
    }


    // Function to add a new fact-checker
    function addFactChecker(address _factChecker, string _identity) {
        // --- VALIDATE IDENTITY BEFORE ADDING (off-chain)
        require(!findIdentity(_identity), "IDENTITY already exists");
        require(!findFactChecker(_factChecker), "ADDRESS already exists");

        factCheckers.push(_factChecker);
        probation[_factChecker] = 0.3;
        reputations[_factChecker] = 1;
        correct_votes[_factChecker] = 0;
        incorrect_votes[_factChecker] = 0;

        // HAS 0.5 weight in all category initially
        for(uint i=0; i<categories.length; i++) {
            weights[_factChecker][categories[i]] = 0.5;
        }
    }


    // AUTOMATICLALY CALLED AFTER CERTAIN TIME
    function end_probabtion(address _factChecker) {
        // REQUIRE('some time elapsed from start of voting until now')

        probation[_factChecker] = 1;

        // IF NOT ENOUGH REPUTATION ACCUMULATED, FACTCHECKER INVALIDATED
        if (reputations[_factChecker] <= 20) {
            // REMOVE VOTER FROM VALID VOTERS
            uint i = 0;
            for (; i < factCheckers.length; i++) {
                if (factCheckers[i] == _factChecker)
                    break;
            }
            factCheckers[i] = factCheckers[factCheckers.length - 1];
            factCheckers.pop();
        }
    }
    

    // CALL PERIODICALLY -- done off-chain
    function periodic() {
        for (; i < factCheckers.length; i++) {
            address a = factCheckers[i];
            // reduce reputations
            reputations[a] = max(0, reputations[a]-5);
        }
    }


    // Function to query the category of a news item
    function getNewsItemCategory(string _itemHash) public view returns (string) {
        return newsItems[_itemHash].category;
    }
    
}
